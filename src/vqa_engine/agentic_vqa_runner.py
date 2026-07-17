import argparse
import glob
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import List, Optional

try:
    from google import genai
    from google.genai import types
    from pydantic import BaseModel, Field
    from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
except ImportError:
    print("Error: 'google-genai', 'pydantic', and 'tenacity' packages are required.")
    print("Run: pip install google-genai pydantic tenacity")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# --- Pydantic Models for Structured Outputs ---
class Issue(BaseModel):
    type: str = Field(description="問題のカテゴリ（例: 'Text Overlap', 'Margin Error', 'Overflow'）")
    severity: str = Field(description="問題の深刻度 (low, medium, high, critical)")
    description: str = Field(description="問題の具体的な説明（どこがどのように崩れているか）")

class EvaluationResult(BaseModel):
    status: str = Field(description="UXを損なう致命的なレイアウト崩れが見つかった場合はFAIL、問題なければPASS")
    confidence_score: float = Field(description="評価の自信度（0.0〜1.0）")
    reasoning: str = Field(description="PASS/FAILと判定した全体的な理由・根拠")
    issues: List[Issue] = Field(description="発見された問題点のリスト。statusがPASSの場合は空配列とする。")

def load_system_prompt(prompt_path: str) -> str:
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            content = f.read()
            # If the tag exists, extract it. Otherwise, return the whole content.
            match = re.search(r"<system_prompt>(.*?)</system_prompt>", content, re.DOTALL)
            if match:
                return match.group(1).strip()
            else:
                return content.strip()
    except FileNotFoundError:
        logger.error(f"Error: Prompt file not found at {prompt_path}")
        sys.exit(1)

# Retry logic for external API resilience
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception),
    reraise=True
)
def evaluate_image(client: genai.Client, image_path: str, system_prompt: str, model_name: str) -> dict:
    logger.info(f"Evaluating image: {image_path}")
    try:
        with open(image_path, "rb") as f:
            image_data = f.read()

        image_part = types.Part.from_bytes(
            data=image_data,
            mime_type="image/png"
        )
        
        prompt = "この画像のレイアウトや表示内容を評価し、結果を返してください。"
        
        # Use Structured Outputs (response_schema)
        response = client.models.generate_content(
            model=model_name,
            contents=[image_part, prompt],
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                response_schema=EvaluationResult,
            )
        )
        
        # response.text is guaranteed to match the JSON schema
        return json.loads(response.text)

    except Exception as e:
        logger.error(f"Error evaluating {image_path} after retries: {e}")
        return {"status": "ERROR", "reasoning": str(e), "issues": []}

def main():
    parser = argparse.ArgumentParser(description="Agentic Visual QA Runner")
    parser.add_argument("--img-dir", required=True, help="Directory containing screenshots to evaluate")
    parser.add_argument("--prompt-file", required=True, help="Path to the system prompt markdown file")
    parser.add_argument("--model", default="gemini-2.5-flash", help="Gemini model to use")
    
    # GCP Project ID via environment variable or argument
    parser.add_argument("--project-id", default=os.environ.get("GCP_PROJECT_ID", ""), help="GCP Project ID for Vertex AI")
    parser.add_argument("--location", default="global", help="GCP Location for Vertex AI")
    
    args = parser.parse_args()

    if not args.project_id:
         logger.error("GCP Project ID must be set via --project-id or GCP_PROJECT_ID environment variable.")
         sys.exit(1)

    try:
        # Vertex AI initialization
        client = genai.Client(
            vertexai=True,
            project=args.project_id,
            location=args.location
        )
        logger.info(f"Initialized Gemini Client via Vertex AI (Project: {args.project_id}, Location: {args.location}).")
    except Exception as e:
        logger.error(f"Failed to initialize Gemini Client. Ensure 'gcloud auth application-default login' is run. Error: {e}")
        sys.exit(1)

    image_dir = Path(args.img_dir)
    prompt_path = args.prompt_file

    if not image_dir.exists() or not image_dir.is_dir():
        logger.error(f"Image directory not found: {image_dir}")
        sys.exit(1)

    system_prompt = load_system_prompt(prompt_path)
    image_pattern = str(image_dir / "**" / "*.png")
    image_files = glob.glob(image_pattern, recursive=True)

    if not image_files:
        logger.warning(f"No PNG images found in {image_dir}")
        sys.exit(0)

    has_failures = False
    results = []

    import concurrent.futures

    def process_image(img_path):
        result = evaluate_image(client, img_path, system_prompt, args.model)
        return img_path, result

    # Use ThreadPoolExecutor to evaluate images concurrently
    max_workers = min(10, len(image_files))
    logger.info(f"Starting evaluation of {len(image_files)} images with {max_workers} workers...")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_image = {executor.submit(process_image, img): img for img in image_files}
        
        for future in concurrent.futures.as_completed(future_to_image):
            img_path = future_to_image[future]
            try:
                _, result = future.result()
                status = result.get("status", "ERROR")
                
                results.append({
                    "file": os.path.basename(img_path),
                    "result": result
                })

                if status == "FAIL" or status == "ERROR":
                    logger.error(f"❌ FAILED: {img_path}")
                    logger.error(f"Reasoning: {result.get('reasoning')}")
                    if "issues" in result:
                        for issue in result.get("issues", []):
                            logger.error(f"  - [{issue.get('severity')}] {issue.get('type')}: {issue.get('description')}")
                    has_failures = True
                else:
                    logger.info(f"✅ PASSED: {img_path} (Confidence: {result.get('confidence_score', 'N/A')})")
            except Exception as exc:
                logger.error(f"❌ ERROR evaluating {img_path}: {exc}")
                results.append({
                    "file": os.path.basename(img_path),
                    "result": {"status": "ERROR", "reasoning": str(exc), "issues": []}
                })
                has_failures = True

    print("\n--- Visual QA Summary ---")
    print(f"Total Images: {len(image_files)}")
    print(f"Passed: {len([r for r in results if r['result'].get('status') == 'PASS'])}")
    print(f"Failed/Errors: {len([r for r in results if r['result'].get('status') in ['FAIL', 'ERROR']])}")
    print("-------------------------\n")

    if has_failures:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()