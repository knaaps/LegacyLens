"""Tests for the parser module."""

from pathlib import Path
import tempfile

import pytest

from legacylens.parser.base import FunctionMetadata
from legacylens.parser.java_parser import JavaParser
from legacylens.parser.python_parser import PythonParser


class TestJavaParser:
    """Tests for JavaParser."""
    
    def setup_method(self):
        self.parser = JavaParser()
    
    def test_language(self):
        assert self.parser.language == "java"
        assert self.parser.file_extensions == [".java"]
    
    def test_can_parse(self):
        assert self.parser.can_parse(Path("Foo.java"))
        assert not self.parser.can_parse(Path("foo.py"))
    
    def test_parse_simple_method(self):
        java_code = '''
public class Calculator {
    public int add(int a, int b) {
        return a + b;
    }
}
'''
        with tempfile.NamedTemporaryFile(suffix=".java", delete=False) as f:
            f.write(java_code.encode())
            f.flush()
            
            methods = self.parser.parse_file(Path(f.name))
        
        assert len(methods) == 1
        method = methods[0]
        assert method.name == "add"
        assert method.class_name == "Calculator"
        assert method.qualified_name == "Calculator.add"
        assert method.complexity == 1  # No branches
    
    def test_parse_method_with_branches(self):
        java_code = '''
public class Validator {
    public boolean validate(String input) {
        if (input == null) {
            return false;
        }
        if (input.isEmpty() || input.length() > 100) {
            return false;
        }
        return true;
    }
}
'''
        with tempfile.NamedTemporaryFile(suffix=".java", delete=False) as f:
            f.write(java_code.encode())
            f.flush()
            
            methods = self.parser.parse_file(Path(f.name))
        
        assert len(methods) == 1
        method = methods[0]
        assert method.name == "validate"
        # Complexity: 1 (base) + 2 (ifs) + 1 (||) = 4
        assert method.complexity >= 3
    
    def test_extract_method_calls(self):
        java_code = '''
public class Service {
    public void process(String data) {
        validate(data);
        String result = transform(data);
        save(result);
    }
}
'''
        with tempfile.NamedTemporaryFile(suffix=".java", delete=False) as f:
            f.write(java_code.encode())
            f.flush()
            
            methods = self.parser.parse_file(Path(f.name))
        
        assert len(methods) == 1
        method = methods[0]
        assert "validate" in method.calls
        assert "transform" in method.calls
        assert "save" in method.calls
    
    def test_extract_imports(self):
        java_code = '''
import java.util.List;
import java.util.ArrayList;

public class Example {
    public List<String> getItems() {
        return new ArrayList<>();
    }
}
'''
        with tempfile.NamedTemporaryFile(suffix=".java", delete=False) as f:
            f.write(java_code.encode())
            f.flush()
            
            methods = self.parser.parse_file(Path(f.name))
        
        assert len(methods) == 1
        method = methods[0]
        assert "java.util.List" in method.imports
        assert "java.util.ArrayList" in method.imports


class TestPythonParser:
    """Tests for PythonParser."""
    
    def setup_method(self):
        self.parser = PythonParser()
    
    def test_language(self):
        assert self.parser.language == "python"
        assert self.parser.file_extensions == [".py"]
    
    def test_can_parse(self):
        assert self.parser.can_parse(Path("foo.py"))
        assert not self.parser.can_parse(Path("Foo.java"))
    
    def test_parse_simple_function(self):
        python_code = '''
def add(a, b):
    return a + b
'''
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
            f.write(python_code.encode())
            f.flush()
            
            functions = self.parser.parse_file(Path(f.name))
        
        assert len(functions) == 1
        func = functions[0]
        assert func.name == "add"
        assert func.class_name is None
        assert func.qualified_name == "add"
        assert func.complexity == 1
    
    def test_parse_class_method(self):
        python_code = '''
class Calculator:
    def multiply(self, a, b):
        return a * b
'''
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
            f.write(python_code.encode())
            f.flush()
            
            functions = self.parser.parse_file(Path(f.name))
        
        assert len(functions) == 1
        func = functions[0]
        assert func.name == "multiply"
        assert func.class_name == "Calculator"
        assert func.qualified_name == "Calculator.multiply"
    
    def test_parse_function_with_branches(self):
        python_code = '''
def validate(data):
    if data is None:
        return False
    if len(data) == 0 or len(data) > 100:
        return False
    return True
'''
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
            f.write(python_code.encode())
            f.flush()
            
            functions = self.parser.parse_file(Path(f.name))
        
        assert len(functions) == 1
        func = functions[0]
        # Complexity: 1 (base) + 2 (ifs) + 1 (or) = 4
        assert func.complexity >= 3
    
    def test_extract_function_calls(self):
        python_code = '''
def process(data):
    validate(data)
    result = transform(data)
    save(result)
'''
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
            f.write(python_code.encode())
            f.flush()
            
            functions = self.parser.parse_file(Path(f.name))
        
        assert len(functions) == 1
        func = functions[0]
        assert "validate" in func.calls
        assert "transform" in func.calls
        assert "save" in func.calls


class TestFunctionMetadata:
    """Tests for FunctionMetadata dataclass."""
    
    def test_qualified_name_with_class(self):
        meta = FunctionMetadata(
            name="foo",
            file_path="/test.java",
            start_line=1,
            end_line=5,
            code="void foo() {}",
            language="java",
            class_name="Bar",
        )
        assert meta.qualified_name == "Bar.foo"
    
    def test_qualified_name_without_class(self):
        meta = FunctionMetadata(
            name="foo",
            file_path="/test.py",
            start_line=1,
            end_line=5,
            code="def foo(): pass",
            language="python",
        )
        assert meta.qualified_name == "foo"
    
    def test_to_dict(self):
        meta = FunctionMetadata(
            name="test",
            file_path="/test.java",
            start_line=10,
            end_line=20,
            code="void test() {}",
            language="java",
            complexity=5,
            line_count=11,
            calls=["foo", "bar"],
            imports=["java.util.List"],
            class_name="TestClass",
        )
        d = meta.to_dict()
        
        assert d["name"] == "test"
        assert d["qualified_name"] == "TestClass.test"
        assert d["complexity"] == 5
        assert d["calls"] == "foo,bar"  # Joined for ChromaDB
        assert d["imports"] == "java.util.List"
