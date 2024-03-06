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

app = FastAPI()

load_dotenv()

url = ""
if "MONGO_URL" in os.environ:
    url = os.getenv("MONGO_URL")
else:
    user = quote(os.getenv("MONGO_USER"))
    pw = quote(os.getenv("MONGO_PASSWORD"))
    hosts = quote(os.getenv("MONGO_HOSTS"))
    auth_src = quote(os.getenv("MONGO_HOSTS_AUTH_SRC"))
    # hosts=','.join(['mongoSber3.multitender.ru:8635', 'mongoSber3.multitender.ru:8635']),
    url = f'mongodb://{user}:{pw}@{hosts}/?authSource={auth_src}'

tlsCAFile = os.getenv("MONGO_CA_FILE")

client = pymongo.MongoClient(
    url,
    tls=True,
    authMechanism="SCRAM-SHA-1",
    tlsAllowInvalidHostnames=True,
    tlsCAFile=tlsCAFile)

db = client.medet
collection = db.issues


class Issue(BaseModel):
    title: str
    document: str | None = None
    incentive: float
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
            "incentive": [],
            "website": issue.website,
            "author": issue.author
        }
    }
    document["issue"]["incentive"].append({issue.author: float(issue.incentive)})
    response = collection.insert_one(document)
    ct = datetime.datetime.now()
    result = {
        "id": str(response.inserted_id),
        "timestamp": ct.timestamp()
    }

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

    collection.update_one({"_id": _id}, new_values)
    return None


class LikeParams(BaseModel):
    id: str
    incentive: float
    author: str


@app.post("/like")
def like(like_params: LikeParams):
    _id = ObjectId(like_params.id)
    document = collection.find_one({"_id": _id})
    document["issue"]["incentive"].append({like_params.author: float(like_params.incentive)})
    new_values = {"$set": {"issue.incentive": document["issue"]["incentive"]}}
    collection.update_one({"_id": _id}, new_values)
    # print(issue)
    document = collection.find_one({"_id": _id})
    document["_id"] = str(document["_id"])
    return document


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
    document = collection.find_one({"_id": _id})
    if glom.glom(document, "implementations", default=None):  # before was implementations
        implementation_ids = [implementation["id"] for implementation in document["implementations"]]
        last_implementation_id = max(implementation_ids)
        implementation["id"] = last_implementation_id + 1
        document["implementations"].append(implementation)
    else:  # first implementation
        implementation["id"] = 1
        document["implementations"] = [implementation]
    new_values = {"$set": {"implementations": document["implementations"]}}
    collection.update_one({"_id": _id}, new_values)
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
    document = collection.find_one({"_id": _id})
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
    collection.update_one({"_id": _id}, new_values)


@app.get("/pass")
def passed(issueId: str, implementationId: int):
    _id = ObjectId(issueId)
    document = collection.find_one({"_id": _id})
    implementations = document["implementations"]
    for implementation_number in range(len(implementations)):
        if implementations[implementation_number]["id"] == implementationId:
            implementations[implementation_number]["phase"] = "prod"
            break
    new_values = {"$set": {"implementations": document["implementations"]}}
    collection.update_one({"_id": _id}, new_values)


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
    document = collection.find_one({"_id": _id})
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
                collection.update_one({"_id": _id}, new_values)

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
    response = collection.find(q)
    response = list(response)
    for site_number in range(len(response)):
        response[site_number]["_id"] = str(response[site_number]["_id"])
    # result = json.dumps(response)
    return response


print(collection.find_one())
value = {
    "title": "title",
    "document": "text",
    "incentive": "555",
    "website": "goolge.com",
    "author": "angry_user"}
# add(title="title", document="text", incentive="444", website="goolge.com", author="angry user")
# print(add(**value))
# print(get_list(["goolge.com", "from.com"]))
# new_value = {
#     "_id": "65e3232858c41d4e2a164023",
#     "title": "title2",
#     "document": "text2",
#     "author": "angry user2"}
# update(**new_value)

# new_value = {
#     "_id": "65e350e2e7e6435f9f4ccff9",
#     "incentive": "5.678",
#     "author": "angry_user33"}
# print(like(**new_value))

# new_value = {
#     "source": {
#         "url": "github link new",
#         "testBranch": "test",
#         "testCommit": "commitId",
#     },
#     "issueId": "65e350e2e7e6435f9f4ccff9",
#     "payment": {
#         "value": 123,
#         "type": "perMonth",
#     },
#     "distributions": ["0x0123"],
#     "testConstructor": "link to the javascript code to load into the web page if any"
# }
# print(push_implementation(**new_value))
