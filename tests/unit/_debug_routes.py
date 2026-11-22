def test_dump_decode_route(make_client):
    client = make_client()
    app = client.app

    def find_route(routes, path):
        for r in routes:
            if getattr(r, "path", None) == path:
                return r
            orig = getattr(r, "original_router", None)
            if orig is not None:
                inner = getattr(orig, "routes", None)
                if inner is not None:
                    found = find_route(inner, path)
                    if found is not None:
                        return found
        return None

    route = find_route(app.routes, "/api/decode")
    dep = route.dependant
    for attr in [
        "body_params",
        "path_params",
        "query_params",
        "cookie_params",
        "header_params",
        "request_param_name",
    ]:
        val = getattr(dep, attr, None)
        print(f"  {attr}:")
        if val:
            for v in val:
                print(f"    {v}")
                fi = getattr(v, "field_info", None)
                if fi:
                    print(f"      field_info type={type(fi).__name__}")
                    mfs = getattr(fi, "max_file_size", None)
                    ml = getattr(fi, "max_length", None)
                    print(f"      max_file_size={mfs} max_length={ml}")
        else:
            print("    (empty)")
