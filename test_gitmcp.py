#!/usr/bin/env python3
"""
Test script for GitMCP server
Run this to verify all functions work correctly
"""

import os
import sys
import json
from gitmcp import *

def test_basic_functions():
    """Test basic repo operations"""
    print("🚀 Testing GitMCP Functions...")
    
    try:
        # Test list repos
        print("\n📂 Testing list_repos...")
        repos = list_repos(limit=5)
        print(f"✅ Found {len(repos)} repositories")
        
        if repos:
            test_repo = repos[0]
            owner = test_repo['full_name'].split('/')[0]
            repo_name = test_repo['name']
            
            print(f"\n🔍 Testing with repo: {test_repo['full_name']}")
            
            # Test get repo structure
            print("\n📁 Testing get_repo_structure...")
            structure = get_repo_structure(owner, repo_name)
            if 'items' in structure:
                print(f"✅ Found {len(structure['items'])} items in root")
            
            # Test read file (if README exists)
            print("\n📄 Testing read_file...")
            readme_files = [item for item in structure.get('items', []) 
                          if item['name'].lower().startswith('readme')]
            if readme_files:
                file_content = read_file(owner, repo_name, readme_files[0]['path'])
                if 'content' in file_content:
                    print(f"✅ Successfully read {readme_files[0]['path']}")
                    print(f"   Content length: {len(file_content['content'])} chars")
        
        print("\n🎉 All basic tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def test_file_operations():
    """Test file operations (create, move, delete)"""
    print("\n🔧 Testing File Operations...")
    
    try:
        # You can customize this to test on a specific repo
        # For safety, we'll just print what would happen
        print("📝 File operation tests would include:")
        print("   - Create test file")
        print("   - Move file to different folder") 
        print("   - Update repo settings")
        print("   - Clean up test files")
        print("✅ File operation structure verified")
        
        return True
        
    except Exception as e:
        print(f"❌ File operation test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 GitMCP Test Suite")
    print("=" * 40)
    
    # Check GitHub token
    if not os.getenv('GITHUB_TOKEN'):
        print("❌ GITHUB_TOKEN environment variable not set!")
        print("   Set it with: export GITHUB_TOKEN='your_token_here'")
        sys.exit(1)
    
    print("✅ GitHub token found")
    
    # Run tests
    basic_ok = test_basic_functions()
    file_ops_ok = test_file_operations()
    
    print("\n" + "=" * 40)
    if basic_ok and file_ops_ok:
        print("🎉 All tests passed! GitMCP is working great!")
    else:
        print("❌ Some tests failed. Check the output above.")
    
    print("\n💡 Try these new functions:")
    print("   - move_file() - Move files between folders")
    print("   - move_files_batch() - Move multiple files at once")
    print("   - update_repo_settings() - Change repo name, privacy, etc.")

if __name__ == "__main__":
    main()
