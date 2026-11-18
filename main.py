from fastapi import FastAPI

from fastapi.middleware.cors import CORSMiddleware

from database.database import SessionLocal
from database.init_db import init_db
from models.upstox_user_login import AccessToken

from api.routes.websocket_market_data_routes import router as market_data_router


from api.routes.upstox_login_routes import (
    router as upstox_router
)

from api.routes.account_funds_user_routes import (
    router as account_funds_router
)

from api.routes.account_funds_payments_routes import (
    router as account_funds_payments_router
)

from api.routes.order_trading_routes import (
    router as order_trading_router
)


from api.routes.gtt_order_routes import router as gtt_order_router

from api.routes.ipo_orders_routes import router as ipo_orders_router


from api.routes.instrument_routes import (
    router as instrument_router
)


from api.routes.index_data_routes import (
    router as index_data_router
)


from api.routes.initial_data_routes import (
    router as initial_data_router
)

from api.routes.backend_table_routes import (
    router as backend_table_router
)


app = FastAPI(
    title="Upstox API"
)


@app.on_event("startup")
def startup():
    init_db()

    # db = SessionLocal()
    # try:
    #     db.query(AccessToken).delete(synchronize_session=False)
    #     db.commit()
    # except Exception:
    #     db.rollback()
    #     raise
    # finally:
    #     db.close()


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



app.include_router(market_data_router)

app.include_router(instrument_router)

app.include_router(upstox_router)


app.include_router(account_funds_router)

app.include_router(account_funds_payments_router)

app.include_router(order_trading_router)

app.include_router(gtt_order_router)

app.include_router(ipo_orders_router)

app.include_router(index_data_router)

app.include_router(initial_data_router)

app.include_router(backend_table_router)


@app.get("/")
def root():

    return {
        "message": "API Running"
    }
