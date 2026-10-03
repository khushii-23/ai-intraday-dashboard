from core.database import Base, engine
import core.models

if __name__ == "__main__":
    print("Creating all tables in intraday.db...")
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully.")