import os
from fastapi import Header, HTTPException, status
from fastapi.responses import JSONResponse

class AppException(HTTPException):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(status_code=status_code, detail=message)
        self.code = code
        self.message = message

def verify_api_key(x_api_key: str = Header(None, alias="X-API-Key")):
    expected_key = os.getenv("API_KEY", "wanganteng")
    if not x_api_key or x_api_key != expected_key:
        raise AppException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="UNAUTHORIZED",
            message="X-API-Key tidak valid"
        )
    return x_api_key
