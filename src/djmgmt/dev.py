if __name__ == '__main__':
    from . import encode, common
    import asyncio
    
    # logs
    common.configure_log(path=__file__)
    
    # dev script
    r = asyncio.run(encode.encode_lossless('/Users/zachvp/Music/DJ/',
                                           '/Users/zachvp/Music/conversion output/re-encoded/',
                                           store_path_dir='/Users/zachvp/developer/scripts/djmgmt/state/output',
                                           store_skipped=True,
                                           encode_always=True))
    print(r)