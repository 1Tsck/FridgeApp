from fastapi import Request, HTTPException, Depends
import firebase_admin
from firebase_admin import auth, credentials, firestore
import os
import json

# firestore init
if not firebase_admin._apps:
    if "FIREBASE_PROJECT_ID" in os.environ:
        cred = credentials.Certificate({
            "type": "service_account",
            "project_id": os.environ["FIREBASE_PROJECT_ID"],
            "private_key": os.environ["FIREBASE_PRIVATE_KEY"].replace("\\n", "\n"),
            "client_email": os.environ["FIREBASE_CLIENT_EMAIL"],
            "token_uri": "https://oauth2.googleapis.com/token",
        })
    else:
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cred = credentials.Certificate(os.path.join(BASE_DIR, "app/sec/fridgeapp-5c204-firebase-adminsdk-fbsvc-d1394347c8.json"))
    firebase_admin.initialize_app(cred, {"storageBucket": "fridgeapp-5c204.appspot.com"})
db = firestore.client()

# users check
async def get_current_user(request: Request):
    # take current user's token
    token = request.cookies.get('token') or request.headers.get('Authorization')
    # if there is no token, the user is not signed in and is informed about that
    if not token:
        raise HTTPException(status_code=401, detail='Not authenticated')
    # token: "Bearer: "+ user_info, user info is separated and verified in Firebse
    try:
        if token.startswith('Bearer '):
            token = token.split(' ', 1)[1]
        decoded = auth.verify_id_token(token)
    # if unrecognized by Firebase, the user is informed about that
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Unauthorized: {e}")
    # user's identification string (uid) is separated from user info
    uid = decoded["uid"]
    
    # user is located in the users collection 
    # separate from the uthentication but sharing uids
    # the information is passed to this backend
    user_ref = db.collection("users").document(uid)
    user_doc = user_ref.get()

    # the user's data is transformed from a stream to a dictionary
    if not user_doc.exists:
        user_data = dict()
    else:
        user_data = user_doc.to_dict()
    
    # uid is added to that dictionary
    user_data["uid"] = uid
    return user_data

# admin role check
# call the function to get current user's data verifying the user in the proccess
async def require_admin(user=Depends(get_current_user)):
    # check the field 'is_admin' downloaded from the database
    if not user.get('admin', False) and not user.get('is_admin', False):
        # if the user is not an admin, trigger exception
        raise HTTPException(status_code=403, detail='Admin required')
    return user
