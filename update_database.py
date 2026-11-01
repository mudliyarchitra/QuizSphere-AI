from app import app, db

with app.app_context():

    db.session.execute(
        db.text("ALTER TABLE user ADD COLUMN course VARCHAR(100)")
    )

    db.session.execute(
        db.text("ALTER TABLE user ADD COLUMN year VARCHAR(50)")
    )

    db.session.execute(
        db.text("ALTER TABLE user ADD COLUMN subject VARCHAR(100)")
    )

    db.session.execute(
        db.text("ALTER TABLE user ADD COLUMN experience VARCHAR(100)")
    )

    db.session.execute(
        db.text("ALTER TABLE user ADD COLUMN qualification VARCHAR(200)")
    )

    db.session.commit()

    print("DATABASE UPDATED SUCCESSFULLY!")