from flask import jsonify

from flask_restful import Resource, abort
from app.health_service_scheduler.models import *


class HealthServiceSiteListResource(Resource):
    def get(self):
        site_schema = HealthServiceSiteSchema(many=True)
        sites = HealthServiceSite.query.all()

        return jsonify(site_schema.dump(sites))


class HealthServiceSiteResource(Resource):
    def get(self, id):
        site_schema = HealthServiceSiteSchema()
        site = HealthServiceSite.query.get(id)
        if not site:
            abort(404, message='Site ID={} not found.'.format(id))

        return jsonify(site_schema.dump(site))


class HealthServiceSlotListResource(Resource):
    def get(self):
        slot_schema = HealthServiceSlotSchema(many=True)
        slots = HealthServiceTimeSlot.query.all()

        return jsonify(slot_schema.dump(slots))


class HealthServiceSlotResource(Resource):
    def get(self, id):
        slot_schema = HealthServiceSlotSchema()
        slot = HealthServiceTimeSlot.query.get(id)
        if not slot:
            abort(404, message='Slot ID={} not found.'.format(id))

        return jsonify(slot_schema.dump(slot))


class HealthServiceBookingListResource(Resource):
    def get(self):
        booking_schema = HealthServiceBookingSchema(many=True)
        bookings = HealthServiceBooking.query.all()

        return jsonify(booking_schema.dump(bookings))


class HealthServiceBookingResource(Resource):
    def get(self, id):
        booking_schema = HealthServiceBookingSchema()
        booking = HealthServiceBooking.query.get(id)

        return jsonify(booking_schema.dump(booking))


class HealthServiceAppUserResource(Resource):
    def get(self, id):
        user_schema = HealthServiceAppUserSchema()
        user = HealthServiceAppUser.query.get(id)

        return jsonify(user_schema.dump(user))


class HealthServiceServiceListResource(Resource):
    def get(self):
        service_schema = HealthServiceServiceSchema(many=True)
        services = HealthServiceService.query.all()

        return jsonify(service_schema.dump(services))


class HealthServiceServiceResource(Resource):
    def get(self, id):
        service_schema = HealthServiceServiceSchema()
        service = HealthServiceService.query.get_or_404(id)

        return jsonify(service_schema.dump(service))
