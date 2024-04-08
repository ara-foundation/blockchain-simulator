# start in terminal uvicorn blockchain_backend:app --reload
import glom
import pymongo
from urllib.parse import quote_plus as quote
from dotenv import load_dotenv
import datetime
import json
from bson.objectid import ObjectId
import os
from fastapi import FastAPI, Query
from pydantic import BaseModel
from typing_extensions import TypedDict
from typing import List
import pandas as pd

hour_pay_contract_id = "65f60e025a2ee015714b0c1a"

app = FastAPI()

load_dotenv()

url = ""
if "MONGO_URL" in os. environ:
    url = os.getenv("MONGO_URL")
else:
    user = quote(os.getenv("MONGO_USER"))
    pw = quote(os.getenv("MONGO_PASSWORD"))
    hosts = quote(os.getenv("MONGO_HOSTS"))
    auth_src = quote(os.getenv("MONGO_HOSTS_AUTH_SRC"))
    url = f'mongodb://{user}:{pw}@{hosts}/?authSource={auth_src}'
    tlsCAFile = os.getenv("MONGO_CA_FILE")

client = pymongo.MongoClient(
    url,
    tls=True,
    authMechanism="SCRAM-SHA-1",
    tlsAllowInvalidHostnames=True)

db = client.medet
issues = db.issues
transactions = db.transactions
smart_contracts = db.smartContracts


class Issue(BaseModel):
    title: str
    document: str | None = None
    incentive: dict[str, float]
    website: str
    author: str


@app.post("/add")
def add(issue: Issue):
    """
    params:
        "title": "required string",
        "document": "optionally explain the description",
        "incentive": 123.45,
        "website": "google.com",
        "author": 0x123
    :return:
        "id":
        "timestamp":
    """
    document = {
        "issue": {
            "title": issue.title,
            "document": issue.document,
            "incentive": issue.incentive,
            "website": issue.website,
            "author": issue.author
        }
    }
    if issue.author not in issue.incentive:
        return "No incentive was provided"
    amount = float(issue.incentive[issue.author])
    document["issue"]["incentive"] = {issue.author: amount}
    if get_balance(issue.author) >= amount:
        response = issues.insert_one(document)
        save_transaction(issue.author, "ARA", amount, "ADD")
        ct = datetime.datetime.now()
        result = {
            "id": str(response.inserted_id),
            "timestamp": ct.timestamp()
        }
    else:
        result = "Balance not enough"
    return result


class IssueUpdate(BaseModel):
    id: str
    title: str
    document: str | None = None
    author: str


@app.post("/update")
def update(issue_update: IssueUpdate):
    _id = ObjectId(issue_update.id)
    new_values = {"$set": {}}
    new_values["$set"]["issue.title"] = issue_update.title
    new_values["$set"]["issue.document"] = issue_update.document
    new_values["$set"]["issue.author"] = issue_update.author

    issues.update_one({"_id": _id}, new_values)
    return None


class LikeParams(BaseModel):
    id: str
    incentive: float
    author: str


@app.post("/like")
def like(like_params: LikeParams):
    _id = ObjectId(like_params.id)
    document = issues.find_one({"_id": _id})
    document["issue"]["incentive"][like_params.author] = like_params.incentive
    new_values = {"$set": {"issue.incentive": document["issue"]["incentive"]}}
    if get_balance(like_params.author) >= like_params.incentive:
        issues.update_one({"_id": _id}, new_values)
        save_transaction(like_params.author, "ARA", like_params.incentive, "LIKE")
        document = issues.find_one({"_id": _id})
        document["_id"] = str(document["_id"])
        return document
    else:
        return "Balance not enough"


class Payment(TypedDict):
    type: str
    value: float


class SourcePush(TypedDict):
    url: str
    testBranch: str
    testCommit: str


class PushParams(BaseModel):
    issueId: str
    source: SourcePush
    payment: Payment
    distributions: List[str]
    testConstructor: str


@app.post("/push")
def push_implementation(push_params: PushParams):
    implementation = {}
    _id = ObjectId(push_params.issueId)
    implementation["phase"] = "test"
    implementation["source"] = push_params.source
    implementation["payment"] = push_params.payment
    implementation["distributions"] = push_params.distributions
    implementation["testConstructor"] = push_params.testConstructor
    document = issues.find_one({"_id": _id})
    if glom.glom(document, "implementations", default=None):  # before was implementations
        implementation_ids = [implementation["id"] for implementation in document["implementations"]]
        last_implementation_id = max(implementation_ids)
        implementation["id"] = last_implementation_id + 1
        document["implementations"].append(implementation)
    else:  # first implementation
        implementation["id"] = 1
        document["implementations"] = [implementation]
    new_values = {"$set": {"implementations": document["implementations"]}}
    issues.update_one({"_id": _id}, new_values)
    return implementation["id"]


class SourceCommit(TypedDict):
    testCommit: str


class CommitParams(BaseModel):
    id: str
    source: SourceCommit
    implementationId: int
    payment: Payment | None = None
    distributions: List[str] | None = None
    testConstructor: str | None = None


@app.post("/commit")
def commit_implementation(commit_params: CommitParams):
    _id = ObjectId(commit_params.id)
    document = issues.find_one({"_id": _id})
    implementations = document["implementations"]
    new_implementations = []
    for implementation in implementations:
        if implementation["id"] == commit_params.implementationId:
            print(commit_params)
            implementation["source"]["testCommit"] = commit_params.source["testCommit"]
            if commit_params.payment:
                implementation["payment"] = commit_params.payment
            if commit_params.distributions:
                implementation["distributions"] = commit_params.distributions
            if commit_params.testConstructor:
                implementation["testConstructor"] = commit_params.testConstructor
        new_implementations.append(implementation)
    new_values = {"$set": {"implementations": document["implementations"]}}
    issues.update_one({"_id": _id}, new_values)


@app.get("/pass")
def passed(issueId: str, implementationId: int):
    _id = ObjectId(issueId)
    document = issues.find_one({"_id": _id})
    implementations = document["implementations"]
    for implementation_number in range(len(implementations)):
        if implementations[implementation_number]["id"] == implementationId:
            implementations[implementation_number]["phase"] = "prod"
            break
    new_values = {"$set": {"implementations": document["implementations"]}}
    issues.update_one({"_id": _id}, new_values)


class ProdCommit(TypedDict):
    prodBranch: str
    prodCommit: str


class ProdParams(BaseModel):
    id: str
    implementationId: int
    source: ProdCommit
    prodConstructor: str


@app.post("/prod")
def prod(prod_params: ProdParams):
    _id = ObjectId(prod_params.id)
    document = issues.find_one({"_id": _id})
    implementations = document["implementations"]
    for implementation_number in range(len(implementations)):
        if implementations[implementation_number]["id"] == prod_params.implementationId:
            if implementations[implementation_number]["phase"] != "prod":
                return "Fail: Implementation not in prod stage"
            else:
                implementations[implementation_number]["prodConstructor"] = prod_params.prodConstructor
                for source_key in prod_params.source.keys():  # add prod_source to exist source
                    implementations[implementation_number]["source"][source_key] = prod_params.source[source_key]
                new_values = {"$set": {"implementations": document["implementations"]}}
                # make payment for developers
                rewards = glom.glom(document, "issue.incentive", default=None)
                print(f"debug: rewards: {rewards}")
                if rewards:
                    reward = sum(rewards.values())
                    print(f"debug: reward: {reward}")
                    developers = []
                    developers = glom.glom(implementations[implementation_number], "distributions", default=None)
                    print(f"debug: developers: {developers}")
                    if reward and developers:
                        reward_per_one = reward/len(developers)
                        print(f"debug: reward_per_one: {rewards}")
                        for developer in developers:
                            print(f"debug: developer: {developer}")
                            save_transaction("ARA", developer, reward_per_one, "PROD")
                        issues.update_one({"_id": _id}, new_values)

                # set project if it requires a payment
                if implementations[implementation_number]["payment"]["value"] > 0:
                    projectParams = ProjectParams(issueId=prod_params.id, implementationId=implementations[implementation_number]["id"], price=implementations[implementation_number]["payment"]["value"], distributions=implementations[implementation_number]["distributions"])
                    mut_eval_setProject(projectParams=projectParams)


@app.get("/list")
def get_list(sites: str | None = Query(default=None)):
    if sites:
        sites = json.loads(sites)
        q = {"issue.website": {"$in": sites}}
    else:
        q = {}
    # print(sites)
    # print("sites : ", json.loads(sites))
    sites = ["google.com"]
    response = issues.find(q)
    response = list(response)
    for site_number in range(len(response)):
        response[site_number]["_id"] = str(response[site_number]["_id"])
    # result = json.dumps(response)
    return response

def save_transaction(from_id: str, to_id: str, value: float, transaction_type: str):
    transaction = {"from": from_id, "to": to_id, "value": value, "type": transaction_type}
    transactions.insert_one(transaction)

@app.get("/balance")
def balance(account: str):
    response = {account: get_balance(account)}
    print(response)
    return response

def get_balance(account: str) -> float:
    start_balance = 100
    minus_value = 0
    plus_value = 0
    user_transactions = transactions.find({"$or": [{"from": account}, {"to": account}]})
    user_transactions = pd.DataFrame(user_transactions)
    if user_transactions.empty:
        return start_balance
    else:
        transactions_minus = user_transactions[user_transactions["from"] == account]
        transactions_plus = user_transactions[user_transactions["to"] == account]
        if not transactions_minus.empty:
            minus_value = float(transactions_minus["value"].sum())
        if not transactions_plus.empty:
            plus_value = float(transactions_plus["value"].sum())
        response = start_balance + plus_value - minus_value
        return response

@app.get("/transfer")
def transfer(from_account: str, to_account: str, value: float):
    from_balance = get_balance(from_account)
    if value > from_balance:
        return "From balance not enough"
    save_transaction(from_account, to_account, value, "TRANSFER")
    response = {from_account: get_balance(from_account), to_account: get_balance(to_account)}
    return response

# Smartcontract part
class ProjectParams(BaseModel):
    issueId: str
    implementationId: int
    price: float
    distributions: List[str]

def get_registered(_id: str) -> List | None:
    registered = None
    contract_id = ObjectId(_id)
    contract = smart_contracts.find_one({"_id": contract_id})
    print(contract)
    if contract:
        registered = glom.glom(contract, "registered", default=None)
    return registered

def get_distributions(issueId: str, implementationId: int) -> list | None:
    registered = get_registered(hour_pay_contract_id)
    distributions = None
    df = pd.DataFrame(registered)
    exist_issue = df[
        (df["issueId"] == issueId)
        &
        (df["implementationId"] == implementationId)
    ]
    if not exist_issue.empty:  # delete previous version
        distributions = exist_issue["distributions"].iloc[0]
    return distributions

# For testing only. In the production version it must be called internally.
@app.post("/mut_eval_setProject")
def mut_eval_setProject(projectParams: ProjectParams):
    registered = get_registered(hour_pay_contract_id)
    df = pd.DataFrame(registered)
    exist_issue = df[
        (df["issueId"] == projectParams.issueId)
        &
        (df["implementationId"] == projectParams.implementationId)
    ]
    if not exist_issue.empty:  # delete previous version
        df.drop(
            df[
                (df["issueId"] == projectParams.issueId)
                &
                (df["implementationId"] == projectParams.implementationId)
            ].index
        )
    registered = df.to_dict("records")
    registered.append(dict(projectParams))
    new_values = {"$set": {"registered": registered}}
    smart_contracts.update_one({"_id": ObjectId(hour_pay_contract_id)}, new_values)

def get_deposits(_id: str) -> List | None:
    deposits = None
    contract_id = ObjectId(_id)
    contract = smart_contracts.find_one({"_id": contract_id})
    print(contract)
    if contract:
        deposits = glom.glom(contract, "deposits", default=None)
    return deposits

def add_deposit(issueId: str, implementationId: int, userId: str):
    new_end_time = None
    deposits = get_deposits(hour_pay_contract_id)
    if deposits:
        df = pd.DataFrame(deposits)
        user_deposits = df[
            (df["issueId"] == issueId)
            &
            (df["implementationId"] == implementationId)
            &
            (df["userId"] == userId)
            ]
        if not user_deposits.empty:
            last_end_time = max(user_deposits["endTime"])
            if last_end_time >= datetime.datetime.now():
                new_end_time = last_end_time + datetime.timedelta(hours=1)
    if not new_end_time:
        new_end_time = datetime.datetime.now() + datetime.timedelta(hours=1)
    deposits.append({
        "issueId": issueId,
        "implementationId": implementationId,
        "userId": userId,
        "endTime": new_end_time})
    new_values = {"$set": {"deposits": deposits}}
    smart_contracts.update_one({"_id": ObjectId(hour_pay_contract_id)}, new_values)

@app.get("/mut_eval_deposit")
def mut_eval_deposit(issueId: str, implementationId: int, userId: str):
    price = None

    registered = get_registered(hour_pay_contract_id)
    if registered:
        df = pd.DataFrame(registered)
        exist_issue = df[
            (df["issueId"] == issueId)
            &
            (df["implementationId"] == implementationId)
            &
            (df["userId"] == userId)
        ]

        if not exist_issue.empty:
            # send payment to ARA
            price = float(exist_issue["price"])
            if get_balance(userId) >= price:
                save_transaction(userId, "ARA", price, "pay_per_hour")
                # save deposit info in smart-contract
                add_deposit(issueId, implementationId, userId)

@app.get("/eval_subscribed")
def eval_subscribed(issueId: str, implementationId: int, userId: str) -> bool:
    deposits = get_deposits(hour_pay_contract_id)
    exist_issue = None
    last_end_time = pd.DataFrame()
    if deposits:
        df = pd.DataFrame(deposits)
        exist_deposit = df[
            (df["issueId"] == issueId)
            &
            (df["implementationId"] == implementationId)
            &
            (df["userId"] == userId)
        ]
        if not exist_deposit.empty:
            last_end_time = exist_deposit["endTime"]
    if not last_end_time.empty:
        if max(last_end_time) > datetime.datetime.now():
            return True
    return False

@app.get("/eval_withdrawable")
def eval_withdrawable(issueId: str, implementationId: int) -> float:
    deposits = get_deposits(hour_pay_contract_id)
    exist_issue = None
    last_end_time = pd.DataFrame()
    if deposits:
        df = pd.DataFrame(deposits)
        withdrawable_deposits = df[
            (df["issueId"] == issueId)
            &
            (df["implementationId"] == implementationId)
            &
            (df["endTime"] < datetime.datetime.now())
            ]
        if not withdrawable_deposits.empty:
            registered = get_registered(hour_pay_contract_id)
            if registered:
                registered = pd.DataFrame(registered)
                withdrawable_deposits = withdrawable_deposits.merge(registered, on=["issueId", "implementationId"])
                withdrawable = sum(withdrawable_deposits["price"])
                return withdrawable
    return 0

@app.get("/mut_eval_withdrawToImpl")
def mut_eval_withdrawToImpl(issueId: str, implementationId: int):
    pay_per_one = None
    distributions = None
    amount = eval_withdrawable(issueId, implementationId)
    distributions = get_distributions(issueId, implementationId)
    print("DISTRIBUTIONS: !!!", distributions)
    if distributions:
        pay_per_one = amount / len(distributions)
    if pay_per_one:
        for distribution in distributions:
            save_transaction("ARA", distribution, pay_per_one, "pay for use in 1 hour")


print("Backend stared")


# print(issues.find_one())
# value = {
#     "title": "title",
#     "document": "text",
#     "incentive": "555",
#     "website": "goolge.com",
#     "author": "angry_user"}

