import os
import sys
import json
import re
import yaml
from datetime import datetime
from pathlib import Path

# --- Configuration ---
def find_workspace_root() -> Path:
    env_root = os.environ.get("WORKSPACE_ROOT")
    if env_root:
        return Path(env_root).resolve()
        
    try:
        current = Path(__file__).resolve()
    except NameError:
        current = Path.cwd().resolve()

    # 自身のプロジェクトルートを探すロジック（環境に合わせて調整）
    for parent in [current] + list(current.parents):
        if (parent / ".git").exists():
            return parent
    
    return current.parent.parent

ROOT_DIR = find_workspace_root()
MD_OUTPUT_FILE = ROOT_DIR / "ALL_DOCS_INDEX.md"
JSON_OUTPUT_FILE = ROOT_DIR / "ALL_DOCS_CONTEXT.json"

TARGET_EXTENSIONS = {".md", ".drawio", ".svg", ".png", ".jpg", ".jpeg"}

EXCLUDE_DIRS = {
    "venv", "node_modules", ".pytest_cache", ".git", ".github", 
    ".vscode", ".next", ".swc", "__pycache__",
    "public", "assets", "static", "images", "icons", "temp"
}

EXCLUDE_FILES = {
    "ALL_DOCS_INDEX.md",
    "ALL_DOCS_CONTEXT.json",
    "LICENSE",
    "package-lock.json",
}

# --- Repository Configuration ---
# 組織名や固有のリポジトリリストを環境変数または設定ファイルから読み込むように汎用化
GITHUB_ORG_OR_USER = os.environ.get("GITHUB_ORG_OR_USER", "your-organization-name")
REQUIRED_REPOSITORIES = os.environ.get("REQUIRED_REPOSITORIES", "").split(",") if os.environ.get("REQUIRED_REPOSITORIES") else []

import subprocess

def should_exclude_dir(dir_path: Path) -> bool:
    if dir_path.name in EXCLUDE_DIRS:
        if dir_path.name == "docs" and dir_path.parent != ROOT_DIR:
            return False 
        return True
    return False

def is_meaningful_text(text: str) -> bool:
    if len(text) < 10:
        return False
    symbol_count = len(re.findall(r'[^a-zA-Z0-9ぁ-んァ-ヶ一-龥ー\s]', text))
    if symbol_count > len(text) * 0.3:
        return False
    return True

def extract_markdown_summary(file_path: Path) -> dict:
    summary = {"title": "", "description": "", "last_updated": ""}
    try:
        mtime = os.path.getmtime(file_path)
        dt = datetime.fromtimestamp(mtime)
        summary["last_updated"] = dt.strftime("%Y/%m/%d")

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            
            front_matter_match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', content, re.DOTALL)
            if front_matter_match:
                try:
                    yaml_content = front_matter_match.group(1)
                    front_matter = yaml.safe_load(yaml_content)
                    if isinstance(front_matter, dict):
                        summary["title"] = front_matter.get("title", "")
                        summary["description"] = front_matter.get("description", "")
                except yaml.YAMLError:
                    pass
                content_to_parse = front_matter_match.group(2)
            else:
                content_to_parse = content

            lines = content_to_parse.split('\n')
            in_code_block = False
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                if line.startswith("```"):
                    in_code_block = not in_code_block
                    continue
                if in_code_block:
                    continue
                
                if not summary["title"] and re.match(r"^#{1,2}\s+", line):
                    summary["title"] = re.sub(r"^#{1,2}\s+", "", line)
                    continue
                
                if not summary["description"] and summary["title"] and not line.startswith(("#", "-", "*", ">", "!", "[", "`", "|")):
                    if is_meaningful_text(line):
                        summary["description"] = line[:100] + "..." if len(line) > 100 else line
                        break
    except Exception as e:
        summary["description"] = f"Error reading file: {e}"
        
    return summary

def get_icon_for_file(file_path: Path) -> str:
    ext = file_path.suffix.lower()
    if ext == ".md": return "📘"
    if ext in [".drawio", ".svg"]: return "🖼️"
    if ext in [".png", ".jpg", ".jpeg"]: return "📸"
    return "📄"

def generate_indexes():
    md_content = [
        "# 📚 プロジェクト ドキュメント ダッシュボード",
        "",
        "> 🤖 **AI Agent Notice:** For automated context, read `ALL_DOCS_CONTEXT.json` instead.",
        "",
        "このページは、全リポジトリに分散する仕様書や設計図を集約したインデックスです。",
        "",
        "## 📑 リポジトリ一覧",
        ""
    ]

    json_context = {
        "metadata": {
            "description": "Semantic index of all documentation across repositories.",
            "root_path": str(ROOT_DIR)
        },
        "repositories": {}
    }

    repo_files = {}

    for root, dirs, files in os.walk(ROOT_DIR):
        root_path = Path(root)
        dirs[:] = [d for d in dirs if not should_exclude_dir(root_path / d)]

        for file in files:
            file_path = root_path / file
            if file in EXCLUDE_FILES:
                continue

            is_target = any(file.lower().endswith(ext) for ext in TARGET_EXTENSIONS)
            if not is_target:
                continue

            relative_to_root = file_path.relative_to(ROOT_DIR)
            parts = relative_to_root.parts
            repo_name = parts[0] if len(parts) > 1 else "Root"

            if repo_name not in repo_files:
                repo_files[repo_name] = []
            
            repo_files[repo_name].append(file_path)

    for repo_name in sorted(repo_files.keys()):
        anchor = repo_name.lower().replace(" ", "-")
        md_content.append(f"- [{repo_name}](#{anchor})")
    md_content.append("\n---")

    for repo_name in sorted(repo_files.keys()):
        files_in_repo = sorted(repo_files[repo_name])
        
        md_content.append(f"\n## <a id=\"{repo_name.lower().replace(' ', '-')}\"></a>{repo_name}\n")
        md_content.append(f"<details>\n<summary><b>📦 {repo_name} のドキュメントを展開する</b> ({len(files_in_repo)} files)</summary>\n")
        
        json_context["repositories"][repo_name] = {"files": []}
        
        grouped_files = {}
        for fp in files_in_repo:
            try:
                rel_to_repo = fp.relative_to(ROOT_DIR / repo_name if repo_name != "Root" else ROOT_DIR)
                parent_dir = rel_to_repo.parent.as_posix()
            except ValueError:
                parent_dir = "."
            
            if parent_dir not in grouped_files:
                grouped_files[parent_dir] = []
            grouped_files[parent_dir].append(fp)
            
        for parent_dir in sorted(grouped_files.keys()):
            display_dir = f"📁 {parent_dir}" if parent_dir != "." else "📁 (ルート直下)"
            md_content.append(f"\n#### {display_dir}\n")
            md_content.append("| Type | Title / File | Summary | Updated |")
            md_content.append("| :---: | :--- | :--- | :---: |")
            
            sorted_files = sorted(grouped_files[parent_dir], key=lambda x: (x.suffix.lower() != ".md", x.name))
            
            for file_path in sorted_files:
                icon = get_icon_for_file(file_path)
                github_url = f"https://github.com/{GITHUB_ORG_OR_USER}/{repo_name}/blob/main/{file_path.relative_to(ROOT_DIR / repo_name if repo_name != 'Root' else ROOT_DIR).as_posix()}"
                
                if file_path.suffix.lower() == ".md":
                    summary = extract_markdown_summary(file_path)
                    title = summary["title"] if summary["title"] else file_path.name
                    desc = summary["description"] if summary["description"] else "-"
                    desc = desc.replace("\n", " ").replace("|", "\\|")
                    date_str = summary["last_updated"]
                    
                    md_content.append(f"| {icon} | **[{title}]({github_url})** | *{desc}* | `{date_str}` |")
                    
                    json_context["repositories"][repo_name]["files"].append({
                        "path": str(file_path.relative_to(ROOT_DIR).as_posix()),
                        "type": ".md",
                        "title": summary["title"],
                        "summary": summary["description"],
                        "last_updated": summary["last_updated"]
                    })
                else:
                    try:
                        mtime = os.path.getmtime(file_path)
                        date_str = datetime.fromtimestamp(mtime).strftime('%Y/%m/%d')
                    except Exception:
                        date_str = "-"
                        
                    md_content.append(f"| {icon} | [{file_path.name}]({github_url}) | - | `{date_str}` |")
                    
                    json_context["repositories"][repo_name]["files"].append({
                        "path": str(file_path.relative_to(ROOT_DIR).as_posix()),
                        "type": file_path.suffix.lower()
                    })
        
        md_content.append("\n</details>\n<br>\n")

    with open(MD_OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(md_content))
    
    with open(JSON_OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(json_context, f, ensure_ascii=False, indent=2)
    
    print(f"Human Index generated at: {MD_OUTPUT_FILE}")
    print(f"AI Semantic Context generated at: {JSON_OUTPUT_FILE}")

if __name__ == "__main__":
    generate_indexes()