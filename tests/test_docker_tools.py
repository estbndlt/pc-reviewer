from tools.docker_tools import docker_df


def test_docker_df_structure():
    data = docker_df()
    assert set(data.keys()) == {'raw'}
    assert isinstance(data['raw'], list)
