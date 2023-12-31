import uuid
from flask import Flask, render_template, redirect, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship 
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///Pomelo.db'
db = SQLAlchemy(app)
Account_ID = 1


# Class definitions

class Account(db.Model):
    __tablename__ = 'accounts'

    id = db.Column(db.Integer, primary_key = True)
    available_credit = db.Column(db.Integer, nullable = False)
    payable_balance = db.Column(db.Integer, default = 0)
    txns = relationship("Transaction", back_populates="account")

    def __repr__(self):
        return '<Account %r>' % self.id


class Transaction(db.Model):
    __tablename__ = 'txns'

    id = db.Column(db.Integer, primary_key = True)
    version_uuid = db.mapped_column(db.String(32), nullable=False)
    amount = db.Column(db.Integer, nullable = False)
    txn_type = db.Column(db.String, nullable = False)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'))
    account = relationship("Account", back_populates="txns")
    date_authorized = db.Column(db.DateTime, default=datetime.utcnow)
    date_settled = db.Column(db.DateTime, default=None)

    __mapper_args__ = {
        "version_id_col": version_uuid,
        "version_id_generator": lambda version: uuid.uuid4().hex,
    }
   
    def __repr__(self):
        return '<Transaction %r>' % self.id


# App routes for navigation

@app.route('/', methods=["GET","POST"])
def index():
    if request.method == "POST":
        return create_txn(request)
    else:
        account = Account.query.get(Account_ID)
        return get_txns(account.id)
    

@app.route('/cancel/<string:id>')
def cancel(id):
    try:
        cancel_txn(id)
        return redirect('/')
    except Exception as e:
        return str(e)
    

@app.route('/settle/<string:id>', methods=["GET","POST"])
def settle(id):
    if request.method == "POST":
        try:
            settle_txn(id, request.form['new_amount'], request.form['version_uuid'])
        except Exception as e:
            return str(e)
        return redirect('/')
    else:
        txn = Transaction.query.get(id)
        return render_template("settle.html", txn=txn)


# API for Transaction CRUD operations

def create_txn(request):
    new_txn = Transaction(
        id = request.form['tid'],
        txn_type = request.form['txn_type'],
        amount = int(float(request.form['amount']) * 100),
        account_id = Account.query.first().id
    )
    if not validate_txn(new_txn):
        return "Bad parameters"
    acnt = Account.query.get(Account_ID)
    if new_txn.txn_type == "Transaction":
        acnt.available_credit -= new_txn.amount
    else:
        acnt.payable_balance += new_txn.amount
    # try:
    db.session.add(new_txn)
    db.session.commit()
    return redirect('/')
    # except:
    #     return "Unable to create transaction."
    

def get_txns(account_id):
    acnt = Account.query.get(account_id)
    txns = Transaction.query.where(Transaction.account_id == account_id).\
        order_by(Transaction.date_authorized)
    return render_template("index.html", acnt=acnt, txns=txns)


def settle_txn(id, new_amount, version_uuid):
    txn = Transaction.query.get_or_404(id)
    if txn.version_uuid != version_uuid:
        raise Exception("Please try again, transaction was recently updated.")
    acnt = Account.query.get(Account_ID)
    new_amount = int(float(new_amount)*100)
    if txn.txn_type == "Transaction":
        acnt.available_credit -= new_amount-txn.amount
        txn.amount = new_amount
        acnt.payable_balance += new_amount
    else:
        acnt.available_credit -= txn.amount
    txn.date_settled = datetime.utcnow()
    db.session.commit()
    

def cancel_txn(id):
    txn = Transaction.query.get_or_404(id, "Transaction no longer presetn in Database")
    acnt = Account.query.get(Account_ID)
    if txn.date_settled:
        raise Exception("Transaction has already been settled")
    if txn.txn_type == "Transaction":
        acnt.available_credit += txn.amount
    else:
        acnt.payable_balance -= txn.amount
    db.session.delete(txn)
    db.session.commit()


def validate_txn(txn:Transaction):
    acnt = Account.query.get(Account_ID)
    if txn.txn_type == "Payment":
        if txn.amount + acnt.payable_balance < 0:
            return False
        if txn.amount >= 0 :
            return False
    else:
        if acnt.available_credit - txn.amount < 0:
            return False
    return True


if __name__ == "__main__":
    app.run(debug = True)