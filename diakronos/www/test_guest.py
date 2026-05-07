import frappe

allow_guest = True
no_cache = 1

def get_context(context):
    context.message = "Hello Guest"
    return context
