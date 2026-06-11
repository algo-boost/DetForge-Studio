"""独立部署：委托 standalone_app（UI + REST + invoke）。"""
from tools.query.standalone_app import create_standalone_app

app = create_standalone_app()

if __name__ == '__main__':
    from tools.query.standalone import main
    main()
