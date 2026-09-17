from edgar import set_identity, Company

set_identity("Owen Taylor owentaylor6075@gmail.com")

company = Company("NYT")
def handleProxyStatement(proxy):
  proxyDir = dir(proxy)
  # print(proxyDir)
  callableArr = []
  for item in proxyDir:
    try:
      val = getattr(proxy,item)
      if(callable(val)):
        callableArr.append(item)
        continue
      print(f"ATTR {item} = {repr(val)[:100]}")
      
    except:
      print('error')
  print(f'callable Methods: {callableArr}')

  
for form in ["DEF 14A", "10-K", "4"]:
  obj = company.get_filings(form=form).latest().obj()
 
  name = type(obj).__name__
  print(f"{form}: {name}")
  
  if(name == "ProxyStatement"):
    handleProxyStatement(obj)
    
