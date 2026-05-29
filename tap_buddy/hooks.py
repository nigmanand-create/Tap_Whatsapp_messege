app_name = "tap_buddy"
app_title = "TAP Buddy"
app_publisher = "Nigam"
app_description = "WhatsApp Automation Platform"
app_email = "activenigma@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "tap_buddy",
# 		"logo": "/assets/tap_buddy/logo.png",
# 		"title": "TAP Buddy",
# 		"route": "/tap_buddy",
# 		"has_permission": "tap_buddy.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/tap_buddy/css/tap_buddy.css"
app_include_js = "/assets/tap_buddy/js/tap_buddy.js"

# include js, css files in header of web template
# web_include_css = "/assets/tap_buddy/css/tap_buddy.css"
# web_include_js = "/assets/tap_buddy/js/tap_buddy.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "tap_buddy/public/scss/website"

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
# app_include_icons = "tap_buddy/public/icons.svg"

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

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "tap_buddy.utils.jinja_methods",
# 	"filters": "tap_buddy.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "tap_buddy.install.before_install"
# after_install = "tap_buddy.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "tap_buddy.uninstall.before_uninstall"
# after_uninstall = "tap_buddy.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "tap_buddy.utils.before_app_install"
# after_app_install = "tap_buddy.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "tap_buddy.utils.before_app_uninstall"
# after_app_uninstall = "tap_buddy.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "tap_buddy.notifications.get_notification_config"

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

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
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

scheduler_events = {
	"cron": {
		"*/10 * * * *": [
			"tap_buddy.tasks.scheduler.process_pending_lms_events",
		],
		"*/5 * * * *": [
			"tap_buddy.tasks.scheduler.process_pending_webhook_events",
		],
		"0,30 * * * *": [
			"tap_buddy.tasks.scheduler.retry_failed_messages",
			"tap_buddy.tasks.scheduler.poll_lms_assignments",
		]
	},
	"hourly": [
		"tap_buddy.tasks.scheduler.sweep_stale_campaigns",
		"tap_buddy.tasks.scheduler.sync_campaign_counts",
		"tap_buddy.tasks.scheduler.process_glific_sync",
		"tap_buddy.tasks.scheduler.sync_lms_schools",
		"tap_buddy.tasks.scheduler.sync_lms_batches",
		"tap_buddy.tasks.scheduler.sync_lms_students",
	],
}

# Testing
# -------

# before_tests = "tap_buddy.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "tap_buddy.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "tap_buddy.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["tap_buddy.utils.before_request"]
# after_request = ["tap_buddy.utils.after_request"]

# Job Events
# ----------
# before_job = ["tap_buddy.utils.before_job"]
# after_job = ["tap_buddy.utils.after_job"]

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
# 	"tap_buddy.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

scheduler_events = {
    "hourly": [
        "tap_buddy.tap_buddy.doctype.tap_buddy_settings.tap_buddy_settings.scheduled_health_check"
    ]
}

