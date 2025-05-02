from app.database import Database, UserModel, TrackedProductModel, TrackingModel

class TestDatabase:
    def test_whatever(self):
        db = Database()
        user = UserModel(tid=288, name="Timur", username="tjann", user_pfp="asfgvsvbwef1234")
        
        
