url = f"https://apis.map.qq.com/ws/geocoder/v1/?address={quote(store['address'])}&output=json&key=XSGBZ-3WQC3-ND23Y-OCBIY-CSSKZ-25FXL"
            
# 发送GET请求
while True:
        response = requests.get(url)
        response.raise_for_status()
        answer = response.json()
        if answer['status'] == 0:
            break
        else:
            time.sleep(1.3)

store['province'] = answer['result']['address_components']['province']
store['city'] = answer['result']['address_components']['city']
store['district'] = answer['result']['address_components']['district']
store['lat'] = answer['result']['location']['lat']
store['lng'] = answer['result']['location']['lng']
store['abcode'] = answer['result']['ad_info']['adcode']