from app import app, db, User, Shipment
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta

def init_db():
    with app.app_context():
        print("Dropping all tables...")
        db.drop_all()
        print("Creating database tables...")
        db.create_all()
        
        # Create admin user
        print("Creating admin user...")
        admin = User(
            username='admin',
            password='admin123',
            is_admin=True
        )
        db.session.add(admin)
        
        # Create test shipments
        print("Creating test shipments...")
        sample_shipments = [
            {
                'tracking_number': 'TEST123',
                'sender_name': 'John Doe',
                'receiver_name': 'Jane Smith',
                'origin': 'New York, USA',
                'destination': 'London, UK',
                'status': 'In Transit',
                'estimated_delivery': datetime.now() + timedelta(days=5),
                'status_updates': [
                    {
                        'status': 'Order Registered',
                        'timestamp': (datetime.now() - timedelta(days=2)).isoformat(),
                        'location': 'New York, USA'
                    },
                    {
                        'status': 'Package Picked Up',
                        'timestamp': (datetime.now() - timedelta(days=1)).isoformat(),
                        'location': 'New York, USA'
                    },
                    {
                        'status': 'In Transit',
                        'timestamp': datetime.now().isoformat(),
                        'location': 'London, UK'
                    }
                ]
            },
            {
                'tracking_number': 'TRK123456',
                'sender_name': 'Alice Johnson',
                'receiver_name': 'Bob Wilson',
                'origin': 'Tokyo, Japan',
                'destination': 'Sydney, Australia',
                'status': 'Delivered',
                'estimated_delivery': datetime.now() - timedelta(days=1),
                'status_updates': [
                    {
                        'status': 'Order Registered',
                        'timestamp': (datetime.now() - timedelta(days=5)).isoformat(),
                        'location': 'Tokyo, Japan'
                    },
                    {
                        'status': 'In Transit',
                        'timestamp': (datetime.now() - timedelta(days=3)).isoformat(),
                        'location': 'Sydney, Australia'
                    },
                    {
                        'status': 'Delivered',
                        'timestamp': datetime.now().isoformat(),
                        'location': 'Sydney, Australia'
                    }
                ]
            }
        ]
        
        for shipment_data in sample_shipments:
            shipment = Shipment(**shipment_data)
            db.session.add(shipment)
        
        try:
            db.session.commit()
            print("Database initialized successfully!")
            # Verify the data
            test_shipment = Shipment.query.filter_by(tracking_number='TEST123').first()
            if test_shipment:
                print("Test shipment created successfully!")
            else:
                print("Warning: Test shipment not found after creation!")
        except Exception as e:
            print(f"Error initializing database: {e}")
            db.session.rollback()

if __name__ == "__main__":
    init_db()
    print("Database initialization completed!")
