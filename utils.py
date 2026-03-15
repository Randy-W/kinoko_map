import requests
from urllib.parse import quote
import os

QQ_MAP_KEY = os.getenv("QQ_MAP_KEY", "")

def get_location_info(address: str):
    """
    Geocodes an address using Tencent Map API.
    Returns a dict with province, city, district, lat, lng, abcode (adcode).
    """
    if not address:
        return None
        
    url = f"https://apis.map.qq.com/ws/geocoder/v1/?address={quote(address)}&output=json&key={QQ_MAP_KEY}"
    
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        if data.get('status') == 0:
            result = data.get('result', {})
            address_components = result.get('address_components', {})
            location = result.get('location', {})
            ad_info = result.get('ad_info', {})
            
            return {
                "province": address_components.get("province"),
                "city": address_components.get("city"),
                "district": address_components.get("district"),
                "lat": location.get("lat"),
                "lng": location.get("lng"),
                "abcode": ad_info.get("adcode")
            }
        else:
            print(f"Map API Error: {data.get('message')}")
            return None
    except Exception as e:
        print(f"Request Error: {e}")
        return None
