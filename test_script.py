try:
    from api import Api
    api = Api()

    def test_call(name, func, *args, **kwargs):
        print(f'--- Testing {name} ---')
        try:
            res = func(*args, **kwargs)
            count = len(res) if isinstance(res, list) else 'N/A'
            print(f'Status: Success, Count: {count}')
        except Exception as e:
            print(f'Status: Failed, Error: {str(e)}')

    test_call('get_explore(page=1, limit=1)', api.get_explore, page=1, limit=1)
    test_call('get_explore(page=1, limit=2)', api.get_explore, page=1, limit=2)
    test_call('get_all_album_data(\"test\", page=1, limit=1)', api.get_all_album_data, 'test', page=1, limit=1)
except Exception as global_e:
    print(f'Global Error: {global_e}')
