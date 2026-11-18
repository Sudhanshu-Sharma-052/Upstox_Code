from database.base import Base
from database.engine import engine

# Import each model so SQLAlchemy registers its table in Base.metadata.
from models.instrument import Instrument
from models.signup_user import User
from models.upstox_user_login import AccessToken, UpstoxUserLogin
from models.order_trading import OrderTrading
from models.multi_order_trading import MultiOrderTrading
from models.gtt_order_model import GTTOrder
from models.backend_table import BackendTable

_REGISTERED_MODELS = (
    Instrument,
    User,
    UpstoxUserLogin,
    AccessToken,
    OrderTrading,
    MultiOrderTrading,
    GTTOrder,
    BackendTable,
)


def init_db():
    """Create any missing tables declared by the application's models."""
    Base.metadata.create_all(bind=engine)
