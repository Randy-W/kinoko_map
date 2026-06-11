from fastapi import FastAPI, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.encoders import jsonable_encoder
from starlette.middleware.base import BaseHTTPMiddleware
from database import init_db, ArcadeStore, ActionToken, Drum
import database
from contextlib import asynccontextmanager
import uvicorn
from typing import Optional
from utils import get_location_info
import re

VALID_DRUM_CONDITIONS = {'', 'gold', 'good', 'good-', 'nom', 'nom-', 'bad'}
VALID_SCREEN_OPTIONS = {'nom', 'c-y', 'c-b', 'c-p', 'streched', 'un-contrast', 'cut', 'bright', 'dark', 'hor-w', 'hor-b', 'ver-w', 'ver-b', 'blur'}

def validate_drum_condition(value: str, field_name: str) -> str:
    if value not in VALID_DRUM_CONDITIONS:
        raise HTTPException(status_code=400, detail=f"Invalid value for {field_name}: {value}")
    return value

def validate_screen(value: str) -> str:
    if value not in VALID_SCREEN_OPTIONS:
        raise HTTPException(status_code=400, detail=f"Invalid screen value: {value}")
    return value

class CacheControlMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "public, max-age=31536000"
        return response

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB on startup
    await init_db()
    yield

app = FastAPI(lifespan=lifespan)
app.add_middleware(CacheControlMiddleware)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# --- Helper Functions ---
async def verify_and_consume_token(token_key: str):
    """
    Verifies if a token exists and has remaining uses.
    Consumes one use if valid.
    """
    if not token_key:
        raise HTTPException(status_code=400, detail="Permission denied: Token required")
        
    token = await ActionToken.find_one(ActionToken.key == token_key)
    if not token:
        raise HTTPException(status_code=403, detail="Invalid Token")
    
    if token.remaining_uses <= 0:
        await token.delete()
        raise HTTPException(status_code=403, detail="Token expired")
    
    token.remaining_uses -= 1
    if token.remaining_uses <= 0:
        await token.delete()
    else:
        await token.save()
    return True

# --- API Endpoints ---

@app.get("/api/token_info")
async def get_token_info(token: str):
    token_obj = await ActionToken.find_one(ActionToken.key == token)
    if token_obj:
        return {"valid": True, "remaining_uses": token_obj.remaining_uses}
    return {"valid": False, "remaining_uses": 0}

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """
    Home page: Lists provinces and cities.
    Fetches the hierarchy of available stores.
    """
    pipeline = [
        {"$match": {"available": True}}, 
        {"$group": {
            "_id": {"province": "$province", "city": "$city"},
            "count": {"$sum": 1}
        }},
        {"$group": {
            "_id": "$_id.province",
            "cities": {"$push": {"name": "$_id.city", "count": "$count"}}
        }},
        {"$sort": {"_id": 1}}
    ]
    
    # helper for sorting cities inside the list
    # Use direct motor access to avoid Beanie/Motor compatibility issues
    if database.db is None:
         # Fallback if db not ready (shouldn't happen with lifespan)
         return HTMLResponse(content="Database connecting...", status_code=503)

    cursor = database.db["arcade_store"].aggregate(pipeline)
    locations = await cursor.to_list(length=None)
    
    for loc in locations:
        if loc.get("cities"):
            loc["cities"].sort(key=lambda x: x["name"] if x["name"] else "")

    return templates.TemplateResponse("index.html", {
        "request": request, 
        "locations": jsonable_encoder(locations)
    })

@app.get("/city/{province}/{city}", response_class=HTMLResponse)
async def city_stores(request: Request, province: str, city: str):
    """
    List stores in a specific city.
    """
    stores = await ArcadeStore.find(
        ArcadeStore.province == province,
        ArcadeStore.city == city,
        ArcadeStore.available == True
    ).sort("-created_at").to_list()
    
    districts = list(set([s.district for s in stores if s.district]))
    districts.sort()
    
    return templates.TemplateResponse("city_stores.html", {
        "request": request,
        "stores": jsonable_encoder(stores),
        "province": province,
        "city": city,
        "districts": districts
    })

@app.get("/store/add", response_class=HTMLResponse)
async def add_store_page(request: Request):
    """
    Render Add Store page.
    """
    return templates.TemplateResponse("add_store.html", {"request": request})

@app.post("/store/add")
async def add_store(
    store_name: str = Form(...),
    address: str = Form(...),
    price_range: Optional[str] = Form(None),
    business_hours: Optional[str] = Form(None),
    local_group: Optional[str] = Form(None),
    cab_count: int = Form(1),
    available: bool = Form(True),
    token: str = Form(...)
):
    """
    Handle adding a new store.
    """
    # 0. Check Token
    await verify_and_consume_token(token)

    # 1. Get Location Info
    location_data = get_location_info(address)
    if not location_data or not location_data.get('abcode'):
        raise HTTPException(status_code=400, detail="Unable to geocode address. Please provide a valid address.")
    
    abcode = str(location_data['abcode'])
    province = location_data.get('province')
    city = location_data.get('city')
    district = location_data.get('district')
    lat = location_data.get('lat')
    lng = location_data.get('lng')

    # 2. Generate ID
    # Find max ID with this abcode prefix
    # Pattern: abcode + 3 digits
    pattern = f"^{abcode}\\d{{3}}$"
    
    # We use direct pymongo query to avoid Beanie regex issues if any, ensuring we get the max ID string
    # Because IDs are strings, lexicographical sort works for numbers of same length
    cursor = database.db["arcade_store"].find(
        {"_id": {"$regex": pattern}}
    ).sort("_id", -1).limit(1)
    
    last_store = await cursor.to_list(length=1)
    
    if last_store:
        last_id = last_store[0]["_id"]
        # Extract suffix
        try:
            suffix = int(last_id[len(abcode):])
            new_suffix = suffix + 1
        except ValueError:
            new_suffix = 1
    else:
        new_suffix = 1
        
    new_id = f"{abcode}{new_suffix:03d}"
    
    # 3. Create Store
    new_store = ArcadeStore(
        id=new_id,
        store_name=store_name,
        address=address,
        province=province,
        city=city,
        district=district,
        abcode=abcode,
        lat=lat,
        lng=lng,
        price_range=price_range,
        business_hours=business_hours,
        local_group=local_group,
        cab_count=cab_count,
        available=available
    )
    
    # 4. Save
    try:
        await new_store.insert()
    except Exception as e:
         # Handle duplicate key error practically (race condition), ideally retry
         raise HTTPException(status_code=500, detail=f"Database Error: {e}")

    return RedirectResponse(url=f"/store/{new_id}", status_code=303)

@app.post("/store/{store_id}/edit")
async def edit_store(
    store_id: str,
    store_name: str = Form(...),
    address: str = Form(...),
    price_range: Optional[str] = Form(None),
    business_hours: Optional[str] = Form(None),
    local_group: Optional[str] = Form(None),
    cab_count: int = Form(1),
    available: bool = Form(True),
    token: str = Form(...)
):
    # 0. Check Token
    await verify_and_consume_token(token)

    store = await ArcadeStore.get(store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
        
    # Check if address changed
    if store.address != address:
        # Re-geocode
        location_data = get_location_info(address)
        if location_data:
            store.province = location_data.get('province')
            store.city = location_data.get('city')
            store.district = location_data.get('district')
            store.lat = location_data.get('lat')
            store.lng = location_data.get('lng')
            store.abcode = str(location_data.get('abcode')) if location_data.get('abcode') else store.abcode
            # ID stays the same even if abcode changes, per common business logic (IDs are immutable usually)
    
    store.store_name = store_name
    store.address = address
    store.price_range = price_range
    store.business_hours = business_hours
    store.local_group = local_group
    store.cab_count = cab_count
    store.available = available
    
    print(f"Updating store {store_id}: Name={store_name}, Available={available}") # Debug log
    await store.save()
    
    return RedirectResponse(url=f"/store/{store_id}", status_code=303)

@app.post("/store/{store_id}/delete")
async def delete_store(store_id: str, token: str = Form(...)):
    # 0. Check Token
    await verify_and_consume_token(token)

    store = await ArcadeStore.get(store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
        
    # Get city info for redirect before deleting
    province = store.province
    city = store.city
    
    await store.delete()
    
    if province and city:
        return RedirectResponse(url=f"/city/{province}/{city}", status_code=303)
    return RedirectResponse(url="/", status_code=303)

@app.post("/store/{store_id}/rate")
async def rate_store(
    store_id: str,
    condition_score: int = Form(...),
    recommendation_score: int = Form(...),
    token: str = Form(...)
):
    # 0. Check Token (Reuse token system to prevent spam, but maybe not strict consume?
    # For now, let's assume rating consumes a token to prevent heavy spam, or maybe just verifies it exists.
    # Instruction didn't specify, but since everything else consumes, let's CONSUME for now to be safe against bots.
    await verify_and_consume_token(token)

    store = await ArcadeStore.get(store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    # Validate scores
    if not (0 <= condition_score <= 5) or not (0 <= recommendation_score <= 5):
        raise HTTPException(status_code=400, detail="Score must be between 0 and 5")

    # Update scores
    store.total_condition_score += condition_score
    store.condition_rating_count += 1
    store.total_recommendation_score += recommendation_score
    store.recommendation_rating_count += 1
    
    await store.save()
    
    return RedirectResponse(url=f"/store/{store_id}", status_code=303)

@app.get("/store/{store_id}", response_class=HTMLResponse)
async def store_detail(request: Request, store_id: str):
    """
    Detail page for a store.
    """
    store = await ArcadeStore.get(store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    drums = await Drum.find(Drum.store_id == store_id).sort("-created_at").to_list()
        
    return templates.TemplateResponse("store_detail.html", {
        "request": request,
        "store": jsonable_encoder(store),
        "drums": jsonable_encoder(drums)
    })


@app.post("/store/{store_id}/drum/add")
async def add_drum(
    store_id: str,
    p1_x_l: str = Form(""),
    p1_o_l: str = Form(""),
    p1_o_r: str = Form(""),
    p1_x_r: str = Form(""),
    p2_x_l: str = Form(""),
    p2_o_l: str = Form(""),
    p2_o_r: str = Form(""),
    p2_x_r: str = Form(""),
    p1_audio: int = Form(0),
    p2_audio: int = Form(0),
    screen: str = Form("nom"),
    track_no: int = Form(1),
    comm: str = Form(""),
    token: str = Form(...)
):
    await verify_and_consume_token(token)
    
    store = await ArcadeStore.get(store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    validate_drum_condition(p1_x_l, "p1_x_l")
    validate_drum_condition(p1_o_l, "p1_o_l")
    validate_drum_condition(p1_o_r, "p1_o_r")
    validate_drum_condition(p1_x_r, "p1_x_r")
    validate_drum_condition(p2_x_l, "p2_x_l")
    validate_drum_condition(p2_o_l, "p2_o_l")
    validate_drum_condition(p2_o_r, "p2_o_r")
    validate_drum_condition(p2_x_r, "p2_x_r")
    validate_screen(screen)
    
    new_drum = Drum(
        store_id=store_id,
        p1_x_l=p1_x_l,
        p1_o_l=p1_o_l,
        p1_o_r=p1_o_r,
        p1_x_r=p1_x_r,
        p2_x_l=p2_x_l,
        p2_o_l=p2_o_l,
        p2_o_r=p2_o_r,
        p2_x_r=p2_x_r,
        p1_audio=p1_audio,
        p2_audio=p2_audio,
        screen=screen,
        track_no=track_no,
        comm=comm
    )
    
    await new_drum.insert()
    
    return RedirectResponse(url=f"/store/{store_id}", status_code=303)


@app.post("/store/{store_id}/drum/{drum_id}/edit")
async def edit_drum(
    store_id: str,
    drum_id: str,
    p1_x_l: str = Form(""),
    p1_o_l: str = Form(""),
    p1_o_r: str = Form(""),
    p1_x_r: str = Form(""),
    p2_x_l: str = Form(""),
    p2_o_l: str = Form(""),
    p2_o_r: str = Form(""),
    p2_x_r: str = Form(""),
    p1_audio: int = Form(0),
    p2_audio: int = Form(0),
    screen: str = Form("nom"),
    track_no: int = Form(1),
    comm: str = Form(""),
    token: str = Form(...)
):
    await verify_and_consume_token(token)
    
    drum = await Drum.get(drum_id)
    if not drum:
        raise HTTPException(status_code=404, detail="Drum not found")
    
    if drum.store_id != store_id:
        raise HTTPException(status_code=400, detail="Drum does not belong to this store")
    
    validate_drum_condition(p1_x_l, "p1_x_l")
    validate_drum_condition(p1_o_l, "p1_o_l")
    validate_drum_condition(p1_o_r, "p1_o_r")
    validate_drum_condition(p1_x_r, "p1_x_r")
    validate_drum_condition(p2_x_l, "p2_x_l")
    validate_drum_condition(p2_o_l, "p2_o_l")
    validate_drum_condition(p2_o_r, "p2_o_r")
    validate_drum_condition(p2_x_r, "p2_x_r")
    validate_screen(screen)
    
    drum.p1_x_l = p1_x_l
    drum.p1_o_l = p1_o_l
    drum.p1_o_r = p1_o_r
    drum.p1_x_r = p1_x_r
    drum.p2_x_l = p2_x_l
    drum.p2_o_l = p2_o_l
    drum.p2_o_r = p2_o_r
    drum.p2_x_r = p2_x_r
    drum.p1_audio = p1_audio
    drum.p2_audio = p2_audio
    drum.screen = screen
    drum.track_no = track_no
    drum.comm = comm
    drum.change_no += 1
    
    await drum.save()
    
    return RedirectResponse(url=f"/store/{store_id}", status_code=303)


@app.post("/store/{store_id}/drum/{drum_id}/delete")
async def delete_drum(store_id: str, drum_id: str, token: str = Form(...)):
    await verify_and_consume_token(token)
    
    drum = await Drum.get(drum_id)
    if not drum:
        raise HTTPException(status_code=404, detail="Drum not found")
    
    if drum.store_id != store_id:
        raise HTTPException(status_code=400, detail="Drum does not belong to this store")
    
    await drum.delete()
    
    return RedirectResponse(url=f"/store/{store_id}", status_code=303)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
