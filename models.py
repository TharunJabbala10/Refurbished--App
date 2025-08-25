from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy()
class Phone(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    brand = db.Column(db.String(50), nullable=False)
    model = db.Column(db.String(50), nullable=False)
    condition = db.Column(db.String(20), nullable=False)
    base_price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, nullable=False)
    listed_on = db.Column(db.String(200), default="")  
    def price_apit(self):
        return round(self.base_price * 0.9, 2) 
    def price_clue(self):
        return round((self.base_price * 0.92) - 2, 2)  
    def price_raptor(self):
        return round(self.base_price * 0.88, 2)  