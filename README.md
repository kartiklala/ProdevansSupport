
uvicorn main:app --host 0.0.0.0 --port 8002 --reload --app-dir backend

streamlit run app.py --server.port=8501


make sure you add your client ID and Secret ID in the format:

```
ZOHO_CLIENT_ID=
ZOHO_CLIENT_SECRET=
ZOHO_REDIRECT_URI=http://localhost:8002/auth/zoho/callback  #add the same in the zoho oauth-setup
ZOHO_REGION=.in
```



