import os
import pytest
from common.yaml_reader import YamlReader

# 测试用临时配置文件
TEST_FILE = "test_temp.yaml"

@pytest.fixture(autouse=True)
def setup_test_file():
    """前置创建测试文件，后置清理"""
    with open(TEST_FILE, "w", encoding="utf-8") as f:
        f.write("""
test:
  key1: value1
  key2:
    nested: nested_value
""")
    YamlReader.clear_cache()
    yield
    if os.path.exists(TEST_FILE):
        os.remove(TEST_FILE)
    YamlReader.clear_cache()

def test_read_file_success():
    """正向：读取文件成功"""
    data = YamlReader.read_file(TEST_FILE, sub_dir=".")
    assert data["test"]["key1"] == "value1"

def test_dot_path_get():
    """正向：点式路径读取嵌套节点"""
    value = YamlReader.get(TEST_FILE, "test.key2.nested", sub_dir=".")
    assert value == "nested_value"

def test_default_value_when_key_missing():
    """反向：节点不存在时返回默认值"""
    value = YamlReader.get(TEST_FILE, "test.not_exist", default="默认值", sub_dir=".")
    assert value == "默认值"
def test_cache_effect():
    """正向：缓存生效，二次读取不重复读盘"""
    YamlReader.read_file(TEST_FILE, sub_dir=".")
    # 缓存键为文件完整绝对路径，拼接对应路径后断言
    abs_path = YamlReader._get_abs_path(".", TEST_FILE)
    assert abs_path in YamlReader._cache
