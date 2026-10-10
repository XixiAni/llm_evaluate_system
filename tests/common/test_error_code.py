from common.error_code import ErrorCode

def test_success_code():
    """正向：验证成功码数值与描述"""
    assert ErrorCode.SUCCESS.code == 0
    assert ErrorCode.SUCCESS.msg == "执行成功"

def test_error_code_hierarchy():
    """正向：验证错误码分层编码规则"""
def test_error_code_hierarchy():
    """正向：验证错误码分层编码规则"""
    # 配置类 1xxx
    assert 1000 < ErrorCode.CONFIG_FILE_NOT_FOUND.code < 2000
    assert 1000 < ErrorCode.CONFIG_KEY_NOT_FOUND.code < 2000
    assert 1000 < ErrorCode.PARAM_EMPTY.code < 2000
    assert 1000 < ErrorCode.API_KEY_MISSING.code < 2000

    # 网络类 2xxx
    assert 2000 < ErrorCode.NETWORK_TIMEOUT.code < 3000
    assert 2000 < ErrorCode.NETWORK_CONNECT_ERROR.code < 3000
    assert 2000 < ErrorCode.HTTP_ERROR.code < 3000
    assert 2000 < ErrorCode.RESPONSE_PARSE_ERROR.code < 3000
    assert 2000 < ErrorCode.NETWORK_UNKNOWN_ERROR.code < 3000

    # 校验类 3xxx
    assert 3000 < ErrorCode.VALID_EMPTY_CONTENT.code < 4000
    assert 3000 < ErrorCode.VALID_LENGTH_NOT_ENOUGH.code < 4000
    assert 3000 < ErrorCode.VALID_HIGH_REPEAT.code < 4000
    assert 3000 < ErrorCode.COMPLIANCE_SENSITIVE_WORD.code < 4000

    # 业务类 4xxx
    assert 4000 < ErrorCode.ANSWER_EXTRACT_FAILED.code < 5000
    assert 4000 < ErrorCode.NO_STANDARD_ANSWER.code < 5000

def test_all_error_codes_unique():
    """边界：验证所有错误码不重复"""
    codes = [item.code for item in ErrorCode]
    assert len(codes) == len(set(codes))

