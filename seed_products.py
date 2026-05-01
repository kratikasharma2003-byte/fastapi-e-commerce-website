import os
from sqlalchemy.orm import Session
from database import SessionLocal
from models import Product

def seed_products():
    db: Session = SessionLocal()
    try:
        # Check if products already exist to avoid duplicates
        if db.query(Product).count() > 0:
            print("Database already has products. Skipping seed.")
            return

        products = [
            Product(
                name="Premium Wireless Headphones",
                description="High-fidelity audio with active noise cancellation and 40-hour battery life. Matte black finish.",
                price=15000.0,
                image_url="/static/images/headphones.png",
                category="Electronics",
                stock=25
            ),
            Product(
                name="Sleek Pro Smartwatch",
                description="Advanced health tracking, GPS, and high-resolution OLED display. Water-resistant up to 50m.",
                price=12000.0,
                image_url="/static/images/smartwatch.png",
                category="Electronics",
                stock=15
            ),
            Product(
                name="Elite Performance Laptop",
                description="Ultra-thin laptop with the latest processor, 16GB RAM, and 512GB SSD. Perfect for professionals.",
                price=85000.0,
                image_url="/static/images/laptop.png",
                category="Computers",
                stock=10
            ),
            Product(
                name="Pro Mirrorless Camera",
                description="Capture stunning photos and 4K videos with this 24.2MP full-frame mirrorless camera.",
                price=125000.0,
                image_url="/static/images/camera.png",
                category="Cameras",
                stock=5
            )
        ]

        db.add_all(products)
        db.commit()
        print("Successfully seeded 4 premium products!")
    except Exception as e:
        db.rollback()
        print(f"Error seeding products: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_products()
