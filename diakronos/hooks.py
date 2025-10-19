app_name = "diakronos"
app_title = "Diakronos"
app_publisher = "Dells Dienste"
app_description = "Eine Gemeindeverwaltungsapp mit um Gemeindemitgliedern im Dienst unter die Arme zu greifen."
app_email = "info@diedells.de"
app_license = "mit"
app_logo_url = "/assets/diakronos/images/diakronos-logo.svg"


fixtures = [
    "Workspace",
    "Module Def",
    "Role",
    "Custom Field",
    "Client Script",
    "Dashboard",
    # ggf. weitere wichtige Typen!
]

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "diakronos",
# 		"logo": "/assets/diakronos/logo.png",
# 		"title": "Diakronos",
# 		"route": "/diakronos",
# 		"has_permission": "diakronos.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/diakronos/css/diakronos.css"
# app_include_js = "/assets/diakronos/js/diakronos.js"

# include js, css files in header of web template
# web_include_css = "/assets/diakronos/css/diakronos.css"
# web_include_js = "/assets/diakronos/js/diakronos.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "diakronos/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "diakronos/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "diakronos.utils.jinja_methods",
# 	"filters": "diakronos.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "diakronos.install.before_install"
# after_install = "diakronos.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "diakronos.uninstall.before_uninstall"
# after_uninstall = "diakronos.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "diakronos.utils.before_app_install"
# after_app_install = "diakronos.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "diakronos.utils.before_app_uninstall"
# after_app_uninstall = "diakronos.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "diakronos.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"diakronos.tasks.all"
# 	],
# 	"daily": [
# 		"diakronos.tasks.daily"
# 	],
# 	"hourly": [
# 		"diakronos.tasks.hourly"
# 	],
# 	"weekly": [
# 		"diakronos.tasks.weekly"
# 	],
# 	"monthly": [
# 		"diakronos.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "diakronos.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "diakronos.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "diakronos.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "diakronos.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["diakronos.utils.before_request"]
# after_request = ["diakronos.utils.after_request"]

# Job Events
# ----------
# before_job = ["diakronos.utils.before_job"]
# after_job = ["diakronos.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"diakronos.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

