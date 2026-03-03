# list all usd plugins and their loaded status
from pxr import Plug
reg = Plug.Registry()
for p in reg.GetAllPlugins():
    # if "omni" in p.name.lower():
    #     print(p.name, "isLoaded =", p.isLoaded)
    print(p.name, "isLoaded =", p.isLoaded)
quit()