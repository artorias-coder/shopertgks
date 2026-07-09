import enum
from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    Text,
    Numeric,
    DateTime,
    ForeignKey,
    Enum,
    Boolean,
    JSON,
    func,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class UserRole(str, enum.Enum):
    CLIENT = "client"
    MANAGER = "manager"
    ADMIN = "admin"
    SUPERADMIN = "superadmin"


class ProductStatus(str, enum.Enum):
    ACTIVE = "active"
    HIDDEN = "hidden"
    OUT_OF_STOCK = "out_of_stock"
    ON_REQUEST = "on_request"
    ARCHIVED = "archived"


class OrderStatus(str, enum.Enum):
    NEW = "new"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    READY = "ready"
    DELIVERING = "delivering"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    PENDING_SYNC = "pending_sync"
    SYNC_ERROR = "sync_error"


class SyncStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCESS = "success"
    ERROR = "error"


class TradeInStatus(str, enum.Enum):
    NEW = "new"
    PROCESSED = "processed"
    CANCELLED = "cancelled"


class GiveawayStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    username = Column(String(100), nullable=True)
    role = Column(Enum(UserRole), default=UserRole.CLIENT, nullable=False)
    consent_newsletter = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    cart = relationship("Cart", back_populates="user", uselist=False)
    orders = relationship("Order", back_populates="user")
    tradeins = relationship("TradeIn", back_populates="user")
    giveaway_participants = relationship("GiveawayParticipant", back_populates="user")


class Shop(Base):
    __tablename__ = "shops"

    id = Column(Integer, primary_key=True)
    livesklad_id = Column(String(100), unique=True, nullable=True)
    name = Column(String(200), nullable=False)
    address = Column(String(500), nullable=True)
    color = Column(String(20), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    product_stocks = relationship("ProductStock", back_populates="shop", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="shop")


class ProductStock(Base):
    __tablename__ = "product_stocks"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    shop_id = Column(Integer, ForeignKey("shops.id"), nullable=False)
    quantity = Column(Integer, default=0, nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    product = relationship("Product", back_populates="stocks")
    shop = relationship("Shop", back_populates="product_stocks")

    __table_args__ = (UniqueConstraint("product_id", "shop_id", name="uix_product_shop_stock"),)


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    image_url = Column(String(1000), nullable=True)
    icon_emoji = Column(String(50), nullable=True)
    tile_size = Column(String(20), default="medium", nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    sku = Column(String(100), unique=True, nullable=False, index=True)
    livesklad_id = Column(String(100), nullable=True)
    name = Column(String(500), nullable=False)
    category = Column(String(200), nullable=True)
    subcategory = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)
    color = Column(String(100), nullable=True)
    memory = Column(String(50), nullable=True)
    specs = Column(JSON, nullable=True)
    price = Column(Numeric(12, 2), nullable=False)
    old_price = Column(Numeric(12, 2), nullable=True)
    discount = Column(Numeric(12, 2), nullable=True)
    stock = Column(Integer, default=0, nullable=False)
    photo_url = Column(String(1000), nullable=True)
    status = Column(Enum(ProductStatus), default=ProductStatus.ACTIVE, nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    cart_items = relationship("CartItem", back_populates="product")
    order_items = relationship("OrderItem", back_populates="product")
    stocks = relationship("ProductStock", back_populates="product", cascade="all, delete-orphan")


class Cart(Base):
    __tablename__ = "carts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", back_populates="cart")
    items = relationship("CartItem", back_populates="cart", cascade="all, delete-orphan")


class CartItem(Base):
    __tablename__ = "cart_items"

    id = Column(Integer, primary_key=True)
    cart_id = Column(Integer, ForeignKey("carts.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, default=1, nullable=False)
    price_snapshot = Column(Numeric(12, 2), nullable=True)

    cart = relationship("Cart", back_populates="items")
    product = relationship("Product", back_populates="cart_items")


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)
    order_number = Column(String(50), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    shop_id = Column(Integer, ForeignKey("shops.id"), nullable=True)
    livesklad_order_id = Column(String(100), nullable=True)
    status = Column(Enum(OrderStatus), default=OrderStatus.NEW, nullable=False)
    total_amount = Column(Numeric(12, 2), nullable=False)
    delivery_type = Column(String(100), nullable=True)
    customer_name = Column(String(255), nullable=True)
    customer_phone = Column(String(50), nullable=True)
    customer_city = Column(String(100), nullable=True)
    comment = Column(Text, nullable=True)
    sync_status = Column(Enum(SyncStatus), default=SyncStatus.PENDING, nullable=False)
    sync_message = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", back_populates="orders")
    shop = relationship("Shop", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    sku = Column(String(100), nullable=False)
    name = Column(String(500), nullable=False)
    quantity = Column(Integer, nullable=False)
    price = Column(Numeric(12, 2), nullable=False)
    total = Column(Numeric(12, 2), nullable=False)

    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")


class SyncLog(Base):
    __tablename__ = "sync_logs"

    id = Column(Integer, primary_key=True)
    source = Column(String(50), nullable=False)
    entity_type = Column(String(50), nullable=True)
    entity_id = Column(String(100), nullable=True)
    status = Column(Enum(SyncStatus), nullable=False)
    message = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class AdminSetting(Base):
    __tablename__ = "admin_settings"

    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class TradeIn(Base):
    __tablename__ = "tradeins"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    device_type = Column(String(100), nullable=False)
    model = Column(String(200), nullable=False)
    battery_condition = Column(String(100), nullable=True)
    device_condition = Column(String(100), nullable=True)
    estimated_price = Column(Numeric(12, 2), nullable=True)
    livesklad_id = Column(String(100), nullable=True)
    status = Column(Enum(TradeInStatus), default=TradeInStatus.NEW, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", back_populates="tradeins")


class Giveaway(Base):
    __tablename__ = "giveaways"

    id = Column(Integer, primary_key=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    prize = Column(String(500), nullable=True)
    status = Column(Enum(GiveawayStatus), default=GiveawayStatus.ACTIVE, nullable=False)
    channel_url = Column(String(1000), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    participants = relationship("GiveawayParticipant", back_populates="giveaway", cascade="all, delete-orphan")


class GiveawayParticipant(Base):
    __tablename__ = "giveaway_participants"

    id = Column(Integer, primary_key=True)
    giveaway_id = Column(Integer, ForeignKey("giveaways.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    tickets = Column(Integer, default=1, nullable=False)
    invited_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    giveaway = relationship("Giveaway", back_populates="participants")
    user = relationship("User", back_populates="giveaway_participants")
