#!/usr/bin/env python3
"""
EDI POC Setup Verification Script
Run this to verify that Phase 3.1 (Setup) completed successfully
"""
import os
import subprocess
import sys
from pathlib import Path

def check_directory_structure():
    """Check if all required directories exist"""
    print("🗂️  Checking directory structure...")
    
    required_dirs = [
        "backend/src/api",
        "backend/src/lib", 
        "backend/src/models",
        "backend/src/services",
        "backend/src/middleware",
        "backend/tests/contract",
        "backend/tests/integration", 
        "backend/tests/unit",
        "backend/tests/performance",
        "backend/tests/fixtures",
        "frontend/src/components",
        "frontend/src/pages", 
        "frontend/src/stores",
        "frontend/src/hooks",
        "frontend/src/lib",
        "frontend/tests/integration",
        "frontend/tests/unit",
    ]
    
    all_exist = True
    for dir_path in required_dirs:
        if Path(dir_path).exists():
            print(f"  ✅ {dir_path}")
        else:
            print(f"  ❌ {dir_path}")
            all_exist = False
    
    return all_exist

def check_backend_files():
    """Check if backend configuration files exist"""
    print("\n🐍 Checking backend files...")
    
    required_files = [
        "backend/main.py",
        "backend/requirements.txt",
        "backend/pyproject.toml",
        "backend/.pre-commit-config.yaml",
        "backend/src/database.py",
        "backend/alembic.ini",
        "backend/migrations/env.py",
        "backend/init_db.py",
        "backend/README.md"
    ]
    
    all_exist = True
    for file_path in required_files:
        if Path(file_path).exists():
            print(f"  ✅ {file_path}")
        else:
            print(f"  ❌ {file_path}")
            all_exist = False
    
    return all_exist

def check_frontend_files():
    """Check if frontend configuration files exist"""
    print("\n⚛️  Checking frontend files...")
    
    required_files = [
        "frontend/package.json",
        "frontend/next.config.js",
        "frontend/tailwind.config.js",
        "frontend/tsconfig.json",
        "frontend/vitest.config.ts",
        "frontend/.eslintrc.json",
        "frontend/.prettierrc",
        "frontend/src/app/layout.tsx",
        "frontend/src/app/page.tsx",
        "frontend/src/app/globals.css",
        "frontend/tests/setup.ts",
        "frontend/README.md"
    ]
    
    all_exist = True
    for file_path in required_files:
        if Path(file_path).exists():
            print(f"  ✅ {file_path}")
        else:
            print(f"  ❌ {file_path}")
            all_exist = False
    
    return all_exist

def check_database_schema():
    """Check database schema setup"""
    print("\n🗄️  Checking database schema...")
    
    try:
        # Check if database module can be imported
        sys.path.append('backend')
        from src.database import Base, File, Mapping, Conversation, ChatMessage, ProcessingJob
        
        # Check if all models are defined
        models = [File, Mapping, Conversation, ChatMessage, ProcessingJob]
        print(f"  ✅ All {len(models)} database models defined")
        
        # Check if migration exists
        if Path("backend/migrations/versions/001_initial_schema.py").exists():
            print("  ✅ Initial migration created")
        else:
            print("  ❌ Initial migration missing")
            return False
            
        return True
        
    except ImportError as e:
        print(f"  ❌ Database import error: {e}")
        return False

def run_basic_checks():
    """Run basic syntax and import checks"""
    print("\n🔍 Running basic checks...")
    
    # Check backend Python syntax
    try:
        result = subprocess.run(
            ["python", "-m", "py_compile", "backend/main.py"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print("  ✅ Backend main.py syntax valid")
        else:
            print("  ❌ Backend syntax error")
            return False
    except Exception as e:
        print(f"  ⚠️  Could not check backend syntax: {e}")
    
    # Check frontend TypeScript config
    if Path("frontend/tsconfig.json").exists():
        print("  ✅ Frontend TypeScript config exists")
    else:
        print("  ❌ Frontend TypeScript config missing")
        return False
    
    return True

def main():
    """Run all verification checks"""
    print("🚀 EDI POC Phase 3.1 Setup Verification")
    print("=" * 50)
    
    checks = [
        ("Directory Structure", check_directory_structure),
        ("Backend Files", check_backend_files),
        ("Frontend Files", check_frontend_files),
        ("Database Schema", check_database_schema),
        ("Basic Checks", run_basic_checks)
    ]
    
    all_passed = True
    
    for check_name, check_func in checks:
        try:
            if not check_func():
                all_passed = False
        except Exception as e:
            print(f"  ❌ {check_name} failed with error: {e}")
            all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("✅ All Phase 3.1 setup checks passed!")
        print("\n📋 Next Steps:")
        print("1. cd backend && pip install -r requirements.txt")
        print("2. cd frontend && npm install") 
        print("3. Backend: uvicorn main:app --reload --port 8000")
        print("4. Frontend: npm run dev")
        print("5. Ready for Phase 3.2 (Tests First)")
    else:
        print("❌ Some setup checks failed. Please review and fix issues above.")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())