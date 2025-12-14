from backend.dependencies import db
from google.cloud import firestore
from collections import defaultdict
from firebase_admin import storage
import uuid
from fastapi import UploadFile
from datetime import datetime, timedelta, timezone


ITEM_TYPES = "item_types"
FRIDGE_ITEMS = "fridge_items"
CART = "cart"
LOG = "change_log"

def get_item_statistics(filter: str, start: str = None, end: str = None):
    now = datetime.now(timezone.utc)

    start_dt = parse_date(start) or (now - timedelta(days=30))
    end_dt = parse_date(end) or now

    # Firestore range query
    logs_ref = (
        db.collection(LOG)
        .where("time", ">=", start_dt)
        .where("time", "<=", end_dt)
    )

    docs = logs_ref.stream()

    # Stats structure
    stats = defaultdict(lambda: {
        "add": 0,
        "delete": 0,
        "modify": 0,
        "user_counts": defaultdict(int)
    })

    # Process each log entry
    for doc in docs:
        data = doc.to_dict()

        item = data.get("item")
        op_type = data.get("op_type")
        user = data.get("user")

        if not item or not op_type or not user:
            continue

        # Count operation types
        if op_type in ["add", "delete", "modify"]:
            stats[item][op_type] += 1

        # Track user activity
        stats[item]["user_counts"][user] += 1

    # Prepare final result
    result = []
    for item, s in stats.items():
        top_user = (
            max(s["user_counts"].items(), key=lambda x: x[1])[0]
            if s["user_counts"]
            else None
        )

        result.append({
            "item": item,
            "add_count": s["add"],
            "delete_count": s["delete"],
            "modify_count": s["modify"],
            "top_user": top_user
        })

    # Apply substring filter
    if filter.strip():
        result = [r for r in result if filter.lower() in r["item"].lower()]

    return result

def list_item_types(filter: str):
    # create a generator for documents in ITEM_TYPES collection
    docs = db.collection(ITEM_TYPES).stream()
    # turn the documents into dictionaries
    all_items = [doc.to_dict() | {"id": doc.id} for doc in docs]
    # apply filter if one is given
    if filter.strip():
        filtered = [i for i in all_items if filter.lower() in i.get("name", "").lower()]
    else:
        filtered = all_items
    return filtered

def list_fridge_items(filter: str):
    return filter_items(FRIDGE_ITEMS, filter)

def list_cart_items(filter: str):
    return filter_items(CART, filter)

def list_change_log(filter: str, start: str = None, end: str = None):
    # get the current date and time
    now = datetime.now(timezone.utc)

    # set the start and end of the time period
    start_dt = parse_date(start) or (now - timedelta(days=30))
    end_dt = parse_date(end) or now

    # conditional query to firebase
    query = (
        db.collection(LOG)
        .where("time", ">=", start_dt)
        .where("time", "<=", end_dt)
    )

    # transform the answear to a processable form
    docs = [doc.to_dict() | {"id": doc.id} for doc in query.stream()]
    if filter.strip():
        docs = [d for d in docs if filter.lower() in d.get("item", "").lower()]

    return docs


def filter_items(collection: str, filter: str):
    docs = db.collection(collection).stream()
    all_items = [doc.to_dict() | {"id": doc.id} for doc in docs]
    if filter.strip():
        filtered_types = list_item_types(filter)
        filtered_types_dict = {item["id"]: item for item in filtered_types}
        filtered = [i for i in all_items if filtered_types_dict.get(i.get("type_id"))]
    else:
        filtered = all_items
    return filtered

def add_item_type(name: str, description: str):
    doc_ref = db.collection(ITEM_TYPES).document()
    doc_ref.set({"name": name, "description": description})

def add_fridge_item(item_type_id: str, quantity: float, unit: str, user: str, add_photo: UploadFile, expiry: str):
    doc_ref = db.collection(FRIDGE_ITEMS).document()
    if not add_photo or isinstance(add_photo, str) or add_photo.filename == "":
        photo_url = None
        blob_name = None
    else:
        photo_url, blob_name = upload_photo(add_photo)
    doc_ref.set({"type_id": item_type_id, "quantity": quantity, "unit": unit, "photo_url": photo_url, "blob_name": blob_name, "expiry_date": expiry})
    #doc_ref.set({"type_id": item_type_id, "quantity": quantity, "unit": unit, "photo_url": photo_url})
    name_ref = db.collection(ITEM_TYPES).document(item_type_id).get(["name"])
    name = name_ref.to_dict().get("name")
    log = db.collection(LOG).document()
    log.set({"op_type":"add", "new_value": "/"+unit+"/"+str(quantity), "old_value":"","changed_value":"/unit/quantity", "item":name, "time":firestore.SERVER_TIMESTAMP, "user":user})

def add_cart_item(item_type_id: str, quantity: float, unit: str, user: str):
    doc_ref = db.collection(CART).document()
    doc_ref.set({"type_id": item_type_id, "quantity": quantity, "unit": unit, "user":user})

# update actions
def update_item_type(item_type_id: str, name: str, description: str):
    doc_ref = db.collection(ITEM_TYPES).document(item_type_id)
    doc_ref.set({"name": name, "description": description}, merge=True)

def update_fridge_item(item_id: str, quantity: float, unit: str, user: str, type_name: str, photo: UploadFile, expiry: str):
    # create a generator for a single document in FRIDGE_ITEMS collection found by its ID
    doc_ref = db.collection(FRIDGE_ITEMS).document(item_id)
    # get the unit and quantity before modifications by turning the document into dictionary and extracting the right field, now key
    old_unit = doc_ref.get().to_dict().get("unit")
    old_quantity = doc_ref.get().to_dict().get("quantity")
    # check for whether document has a photo and if yes, get it's name
    try:
        old_photo = doc_ref.get().to_dict().get("blob_name")
    # if there is no photo, set the link to photo to None
    except Exception:
        old_photo = None

    # if no new photo is given or an old one does not exist, set photo to none and set the other given variables as given
    if not photo or isinstance(photo, str) or photo.filename == "":
        photo_url = None
        doc_ref.set({"quantity": quantity, "unit": unit, "expiry_date": expiry}, merge=True)
    else:
        # if there is a new photo given and an old one exists, delete the old one from the storage and upload a new one
        if old_photo:
            deleted = delete_photo(old_photo)
            if not deleted:
                return "Failed to delete old photo"
        photo_url, blob_name = upload_photo(photo)
        doc_ref.set({"quantity": quantity, "unit": unit, "photo_url": photo_url, "blob_name": blob_name, "expiry_date": expiry}, merge=True)

    log_change(doc_ref, quantity, unit, user, type_name, old_quantity, old_unit, photo_url)

def update_cart_item(cart_id: str, quantity: float, unit: str, user: str):
    doc_ref = db.collection(CART).document(cart_id)
    try:
        doc_ref.set({"quantity": quantity, "unit": unit, "user" :user}, merge=True)
    except:
        return "Failed to update the item"
# delete actions
def delete_item_type(item_type_id: str):
    doc_ref = db.collection(ITEM_TYPES).document(item_type_id)
    photo_url = doc_ref.get().to_dict().get("photo_url")
    delete_photo(photo_url)
    doc_ref.delete()

def delete_fridge_item(item_id: str, user: str, type_name: str):
    #get values
    doc_ref = db.collection(FRIDGE_ITEMS).document(item_id)
    old_ref = doc_ref.get()
    old_unit = old_ref.to_dict().get("unit")
    old_q = old_ref.to_dict().get("quantity")
    #set values
    old_value = "/"+old_unit+"/"+str(old_q)
    new_value = ""
    changed_values = "/unit/quantity"
    try:
        photo_name = old_ref.to_dict().get("blob_name")
        delete_photo(photo_name)
        changed_values+="/photo"
    except Exception:
        None
    doc_ref.delete()
    #log
    log = db.collection(LOG).document()
    log.set({"op_type":"delete","old_value": old_value, "new_value": new_value, "changed_value": changed_values, "item":type_name, "time":firestore.SERVER_TIMESTAMP,"user":user})

def delete_cart_item(cart_id: str):
    doc_ref = db.collection(CART).document(cart_id)
    doc_ref.delete()

def log_change(doc_ref: any, quantity: float, unit: str, user: str, type_name: str, old_quantity: float, old_unit: str, photo_url: str = None):
    # save old values
    # initialize old and new fields
    old_value = ""
    new_value = ""
    changed_values = ""
    # check what"s been changed
    if unit != old_unit:
        old_value += "/"+old_unit
        new_value += "/"+unit
        changed_values +="/unit"
    if quantity != old_quantity:
        old_value += "/"+ str(old_quantity)
        new_value += "/"+ str(quantity)
        changed_values +="/quantity"
    if photo_url:
        changed_values +="/photo"
    # save log to db
    log = db.collection(LOG).document()
    log.set({"op_type":"modify","old_value": old_value, "new_value": new_value, "changed_value": changed_values, "item":type_name, "time":firestore.SERVER_TIMESTAMP, "user":user})


def upload_photo(file):
    bucket = storage.bucket()
    blob_name = f"item_photos/{uuid.uuid4()}_{file.filename}"
    blob = bucket.blob(blob_name)
    blob.upload_from_file(file.file, content_type=file.content_type)
    blob.make_public()
    return blob.public_url, blob_name

def delete_photo(blob_name):
    try:
        bucket = storage.bucket()
        blob = bucket.blob(blob_name)
        blob.delete()
        return True
    except Exception:
        return False
    
def parse_date(date_str: str):
    if not date_str:
        return None
    return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)


'''
def list_change_log(filter: str, start_date: str = None, end_date: str = None):
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    logs = db.collection(LOG).where("time", ">=", cutoff)
    docs = logs.stream()
    all_items = [doc.to_dict() | {"id": doc.id} for doc in docs]
    if filter.strip():
        filtered = [i for i in all_items if filter.lower() in i.get("item", "").lower()]
    else:
        filtered = all_items
    return filtered

def get_item_statistics(filter: str,  start: str = None , end: str = None):
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    logs_ref = db.collection(LOG).where("time", ">=", cutoff)
    docs = logs_ref.stream()
    

    stats = defaultdict(lambda: {"add": 0, "delete": 0, "modify": 0, "user_counts": defaultdict(int)})

    for doc in docs:
        data = doc.to_dict()
        item = data.get("item")
        op_type = data.get("op_type")
        user = data.get("user")

        if not item or not op_type or not user:
            continue
        # Count operation types
        if op_type in stats[item]:
            stats[item][op_type] += 1
        else:
            stats[item][op_type] = 1

        # Count user activity per item
        stats[item]["user_counts"][user] += 1
    # Post-process to find top user per item
    result = []
    for item, s in stats.items():
        top_user = max(s["user_counts"].items(), key=lambda x: x[1])[0] if s["user_counts"] else None
        result.append({
            "item": item,
            "add_count": s["add"],
            "delete_count": s["delete"],
            "modify_count": s["modify"],
            "top_user": top_user
        })
    if filter.strip():
        filtered = [i for i in result if filter.lower() in i.get("item", "").lower()]
    else:
        filtered = result
    return filtered

'''
