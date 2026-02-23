"""
Update imports after moving files to src/ folder
"""
import os
import re

# Files to update
files_to_update = [
    'src/app.py',
    'src/ai_alert_manager.py',
    'src/alert_manager.py',
    'src/correlation_engine.py',
    'src/github_integration.py',
    'tests/test_github_integration.py'
]

# Import mappings (old -> new)
import_mappings = {
    'from alert_manager import': 'from src.alert_manager import',
    'from ai_alert_manager import': 'from src.ai_alert_manager import',
    'from ai_predictor import': 'from src.ai_predictor import',
    'from correlation_engine import': 'from src.correlation_engine import',
    'from github_integration import': 'from src.github_integration import',
    'from issue_integration import': 'from src.issue_integration import',
    'from log_collector import': 'from src.log_collector import',
    'import alert_manager': 'from src import alert_manager',
    'import ai_alert_manager': 'from src import ai_alert_manager',
    'import ai_predictor': 'from src import ai_predictor',
}

def update_file_imports(filepath):
    """Update imports in a single file"""
    if not os.path.exists(filepath):
        print(f"⚠️  File not found: {filepath}")
        return False
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Apply all import mappings
        for old_import, new_import in import_mappings.items():
            content = content.replace(old_import, new_import)
        
        # Only write if changes were made
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ Updated: {filepath}")
            return True
        else:
            print(f"ℹ️  No changes: {filepath}")
            return False
    except Exception as e:
        print(f"❌ Error updating {filepath}: {e}")
        return False

def main():
    print("=" * 60)
    print("Updating imports for src/ folder structure")
    print("=" * 60)
    print()
    
    updated_count = 0
    
    for filepath in files_to_update:
        if update_file_imports(filepath):
            updated_count += 1
    
    print()
    print("=" * 60)
    print(f"✅ Updated {updated_count} files")
    print("=" * 60)
    print()
    print("You can now run: python src\\app.py")

if __name__ == '__main__':
    main()
