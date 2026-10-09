import pytest
from common.yaml_reader import YamlReader

@pytest.fixture(autouse=True)
def setup_test_env(tmp_path):
    """前置在临时目录创建测试文件、清理缓存；文件由 tmp_path 自动回收，无需手动删除"""
    test_file = tmp_path / "test_temp.yaml"
    test_file.write_text("""
test:
  key1: value1
  key2:
    nested: nested_value
""", encoding="utf-8")
    YamlReader.clear_cache()
    yield
    YamlReader.clear_cache()

def test_read_file_success(tmp_path):
    """正向：读取文件成功"""
    data = YamlReader.read_file("test_temp.yaml", sub_dir=str(tmp_path))
    assert data["test"]["key1"] == "value1"

def test_dot_path_get(tmp_path):
    """正向：点式路径读取嵌套节点"""
    value = YamlReader.get("test_temp.yaml", "test.key2.nested", sub_dir=str(tmp_path))
    assert value == "nested_value"

def test_default_value_when_key_missing(tmp_path):
    """反向：节点不存在时返回默认值"""
    value = YamlReader.get("test_temp.yaml", "test.not_exist", default="默认值", sub_dir=str(tmp_path))
    assert value == "默认值"

def test_cache_effect(tmp_path):
    """正向：缓存生效，二次读取不重复读盘"""
    YamlReader.read_file("test_temp.yaml", sub_dir=str(tmp_path))
    # 缓存键为文件完整绝对路径，拼接对应路径后断言
    abs_path = YamlReader._get_abs_path(str(tmp_path), "test_temp.yaml")
    assert abs_path in YamlReader._cache
