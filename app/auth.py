import json
from flask import current_app

def authenticate(username, password):
    if current_app.config["AUTH_MODE"] == "mock":
        return _mock_authenticate(username, password)
    else:
        return _ldap_authenticate(username, password)

def get_managers():
    if current_app.config["AUTH_MODE"] == "mock":
        return _mock_get_managers()
    else:
        return _ldap_get_managers()

def _load_mock_users():
    with open(current_app.config["MOCK_USERS_FILE"]) as f:
        return json.load(f)

def _mock_authenticate(username, password):
    for user in _load_mock_users():
        if user["username"] == username and user["password"] == password:
            return {"username":user["username"],"full_name":user["full_name"],"department":user["department"],"employee_number":user["employee_number"],"is_admin":user.get("is_admin",False),"is_manager":user.get("is_manager",False)}
    return None

def _mock_get_managers():
    return [{"full_name":u["full_name"],"department":u["department"]} for u in _load_mock_users() if u.get("is_manager")]

def _ldap_authenticate(username, password):
    from ldap3 import Server, Connection, ALL, SUBTREE
    cfg = current_app.config
    server = Server(cfg["LDAP_SERVER"], get_info=ALL)
    conn = Connection(server, user=f"{cfg['LDAP_DOMAIN']}\\{username}", password=password)
    if not conn.bind():
        return None
    svc = Connection(server, user=cfg["LDAP_SERVICE_ACCOUNT"], password=cfg["LDAP_SERVICE_PASSWORD"])
    if not svc.bind():
        return None
    svc.search(cfg["LDAP_BASE_DN"], f"(sAMAccountName={username})", attributes=["displayName","department","employeeNumber","memberOf"], search_scope=SUBTREE)
    if not svc.entries:
        return None
    entry = svc.entries[0]
    member_of = str(entry.memberOf)
    return {"username":username,"full_name":str(entry.displayName),"department":str(entry.department),"employee_number":str(entry.employeeNumber),"is_admin":cfg.get("LDAP_ADMINS_GROUP","") in member_of,"is_manager":cfg.get("LDAP_MANAGERS_GROUP","") in member_of}

def _ldap_get_managers():
    from ldap3 import Server, Connection, ALL, SUBTREE
    cfg = current_app.config
    server = Server(cfg["LDAP_SERVER"], get_info=ALL)
    conn = Connection(server, user=cfg["LDAP_SERVICE_ACCOUNT"], password=cfg["LDAP_SERVICE_PASSWORD"])
    if not conn.bind():
        return []
    conn.search(cfg["LDAP_BASE_DN"], f"(memberOf={cfg['LDAP_MANAGERS_GROUP']})", attributes=["displayName","department"], search_scope=SUBTREE)
    return [{"full_name":str(e.displayName),"department":str(e.department)} for e in conn.entries]
