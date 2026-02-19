"""
Sovereign Skill System
======================
Loads Python-based "Action Skills" and Markdown-based "Knowledge Skills".

Usage:
    loader = SkillLoader("skills")
    tools = loader.get_tool_schemas()
    context = loader.get_knowledge_context()
    
    # Execute tool
    result = loader.execute_tool("web_search", {"query": "BTC price"})
"""

import os
import sys
import glob
import json
import inspect
import logging
import importlib.util
from typing import Dict, Any, Callable

logger = logging.getLogger("SkillLoader")

def tool(func):
    """Decorator to mark a function as an Action Skill."""
    func._is_tool = True
    return func

class SkillLoader:
    def __init__(self, skills_dir="skills"):
        self.skills_dir = skills_dir
        self.tools: Dict[str, Callable] = {}
        self.schemas: list = []
        self.knowledge: list = []
        
        # Ensure skills dir exists
        if not os.path.exists(self.skills_dir):
            os.makedirs(self.skills_dir)
            # Create a README
            with open(os.path.join(self.skills_dir, "README.md"), "w") as f:
                f.write("# Sovereign Skills\n\nDrop .py files for tools and .md files for knowledge.")

    def load_skills(self):
        """Scan skills directory for .py and .md files."""
        self.tools = {}
        self.schemas = []
        self.knowledge = []
        
        # 1. Load Action Skills (.py)
        py_files = glob.glob(os.path.join(self.skills_dir, "*.py"))
        for py_file in py_files:
            self._load_python_skill(py_file)
            
        # 2. Load Knowledge Skills (.md)
        md_files = glob.glob(os.path.join(self.skills_dir, "*.md"))
        for md_file in md_files:
            if "README.md" in md_file:
                continue
            self._load_markdown_skill(md_file)
            
        logger.info(f"🧩 Skills Loaded: {len(self.tools)} tools, {len(self.knowledge)} docs")

    def _load_python_skill(self, file_path):
        module_name = os.path.basename(file_path).replace(".py", "")
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if not spec or not spec.loader:
            return
            
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
            
            # Scan for @tool decorated functions
            for name, obj in inspect.getmembers(module):
                if inspect.isfunction(obj) and getattr(obj, "_is_tool", False):
                    self._register_tool(name, obj)
                    
        except Exception as e:
            logger.error(f"❌ Failed to load skill {module_name}: {e}")

    def _register_tool(self, name, func):
        """Convert python function to OpenAI Tool Schema."""
        sig = inspect.signature(func)
        doc = inspect.getdoc(func) or "No description provided."
        
        parameters = {
            "type": "object",
            "properties": {},
            "required": []
        }
        
        for param_name, param in sig.parameters.items():
            param_type = "string"  # Default
            if param.annotation == int:
                param_type = "integer"
            elif param.annotation == float:
                param_type = "number"
            elif param.annotation == bool:
                param_type = "boolean"
                
            parameters["properties"][param_name] = {
                "type": param_type,
                "description": f"Argument: {param_name}"
            }
            if param.default == inspect.Parameter.empty:
                parameters["required"].append(param_name)
                
        schema = {
            "type": "function",
            "function": {
                "name": name,
                "description": doc,
                "parameters": parameters
            }
        }
        
        self.tools[name] = func
        self.schemas.append(schema)
        logger.debug(f"  🔧 Registered tool: {name}")

    def _load_markdown_skill(self, file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                filename = os.path.basename(file_path)
                self.knowledge.append(f"--- SOURCE: {filename} ---\n{content}\n")
        except Exception as e:
            logger.error(f"❌ Failed to load doc {file_path}: {e}")

    def get_tool_schemas(self):
        return self.schemas

    def get_knowledge_context(self):
        if not self.knowledge:
            return ""
        return "\n\n# EXPERT KNOWLEDGE (Skills)\n" + "\n".join(self.knowledge)

    def execute_tool(self, tool_name, args):
        if tool_name not in self.tools:
            return f"Error: Tool '{tool_name}' not found."
        
        try:
            logger.info(f"🛠️ Executing skill: {tool_name}({args})")
            func = self.tools[tool_name]
            result = func(**args)
            return str(result)
        except Exception as e:
            logger.error(f"🔥 Tool error: {e}")
            return f"Error executing {tool_name}: {e}"
