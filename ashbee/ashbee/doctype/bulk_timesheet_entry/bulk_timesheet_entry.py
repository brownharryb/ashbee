# -*- coding: utf-8 -*-
# Copyright (c) 2019, 9t9IT and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils import today
from erpnext.hr.doctype.salary_structure_assignment.salary_structure_assignment import get_assigned_salary_structure


class BulkTimesheetEntry(Document):
	

	def get_employee_details(self, employee):
		employee = frappe.get_doc("Employee", employee)
		return {
					"name":employee.employee_name, 
					"rate":self.get_employee_charge_per_hour(employee)
				}

	def get_project_name(self, project):
		project = frappe.get_doc("Project",project)
		return project.name

	def get_employee_charge_per_hour(self, employee):
		salary_structure = get_assigned_salary_structure(employee.name, today())
		if not salary_structure:
			return 0.0
		salary_structure = frappe.get_doc("Salary Structure", salary_structure)
		if salary_structure.docstatus != 1 or not salary_structure.is_active == "Yes" or \
						not salary_structure.salary_slip_based_on_timesheet:
			return 0.0
		return salary_structure.hour_rate

	def validate(self):
		self.validate_costs()
		
	def before_submit(self):
		self.bulk_delete()
		for detail in self.details:
			self.update_timesheet(detail)
			self.submit_timesheet(detail.timesheet)

	def on_cancel(self):
		for detail in self.details:
			self.cancel_timesheet(detail.timesheet)
			self.delete_timesheet(detail.timesheet)

	def on_trash(self):
		for detail in self.details:
			self.delete_timesheet(detail.timesheet)


	def validate_costs(self):
		for detail in self.details:
			detail.normal_cost = detail.hourly_cost * detail.normal_hours
			detail.ot1 = detail.hourly_cost * detail.ot1_hours * 1.25
			detail.ot2 = detail.hourly_cost * detail.ot2_hours * 1.50
			detail.total_cost = detail.ot1 + detail.ot2 + detail.normal_cost


	def bulk_delete(self):
		filters = {"parent":self.name}
		to_delete = []
		timesheet_details = frappe.get_all("Bulk Timesheet Details",filters={"parent":self.name}, fields=["name","timesheet"])
		for detail in timesheet_details:
			if not self.details or detail.name not in [i.name for i in self.details]:
				self.delete_timesheet(d)

	def submit_timesheet(self, timesheet):
		if not timesheet:
			return
		if isinstance(timesheet, str) or isinstance(timesheet, unicode):
			timesheet = frappe.get_doc("Timesheet", timesheet)
		if timesheet.docstatus == 0:
			timesheet.submit()

	def delete_timesheet(self, timesheet):
		if not timesheet:
			return
		if isinstance(timesheet, str) or isinstance(timesheet, unicode):
			if not self.timesheet_exists(timesheet):
				return
			timesheet = frappe.get_doc("Timesheet", timesheet)
		if timesheet.docstatus == 1:
			timesheet.cancel()
		timesheet.delete()

	def cancel_timesheet(self, timesheet):
		if not timesheet:
			return
		if isinstance(timesheet, str) or isinstance(timesheet, unicode):
			if not self.timesheet_exists(timesheet):
				return
			timesheet = frappe.get_doc("Timesheet", timesheet)
		if timesheet.docstatus == 1:
			timesheet.cancel()

	def timesheet_exists(self, timesheet_name):
		return frappe.db.exists("Timesheet",timesheet_name)


	def update_timesheet(self, detail):
		timesheet = frappe.new_doc("Timesheet")
		timesheet.company = self.company
		timesheet.employee = detail.employee
		timesheet.time_logs = self.get_timesheet_timelogs(timesheet, detail)
		timesheet.save(ignore_permissions=True)
		detail.reload()
		detail.timesheet = timesheet.name
		detail.save()


	def get_timesheet_timelogs(self, timesheet, entry_detail):
		timesheet_details = []
		if not hasattr(timesheet, "time_logs") or not timesheet.time_logs:
			detail = frappe.new_doc("Timesheet Detail")
		else:
			detail = timesheet.time_logs[0]
		detail.parentfield = "time_logs"
		detail.activity_type = self.get_activity_type()
		detail.hours = entry_detail.normal_hours
		detail.from_time = entry_detail.start_date_time
		detail.to_time = entry_detail.end_date_time
		detail.billable = True
		detail.costing_rate = entry_detail.hourly_cost
		detail.costing_amount = entry_detail.total_cost
		detail.project = entry_detail.project
		detail.ashbee_ot = entry_detail.ot1
		detail.ashbee_ot2 = entry_detail.ot2

		timesheet_details.append(detail)
		return timesheet_details

	def get_activity_type(self):
		name = "Labour Hours"
		exists = frappe.db.exists("Activity Type", name)
		if not exists:
			labour_hours = frappe.new_doc("Activity Type")
			labour_hours.activity_type = name
			labour_hours.save(ignore_permissions=True)
		else:
			labour_hours = frappe.get_doc("Activity Type", name)
		return labour_hours.name