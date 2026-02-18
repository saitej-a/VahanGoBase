import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser

logger = logging.getLogger(__name__)


class DriverLocationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time driver location updates.
    
    Connect: ws://host/ws/driver/location/?token=<jwt>
    Send:    {"lng": 78.4867, "lat": 17.3850}
    """

    async def connect(self):
        self.user = self.scope.get('user', AnonymousUser())

        if isinstance(self.user, AnonymousUser) or not self.user.is_authenticated:
            await self.close(code=4001)
            return

        # Verify user is a driver
        self.driver = await self._get_driver()
        if not self.driver:
            await self.close(code=4003)
            return

        self.driver_id = self.driver.id
        self.driver_group = f'driver_{self.driver_id}'

        # Join driver's personal group (for receiving ride requests)
        await self.channel_layer.group_add(self.driver_group, self.channel_name)
        # Join global online drivers group
        await self.channel_layer.group_add('online_drivers', self.channel_name)
        
        await self.accept()
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': f'Driver {self.driver_id} connected',
        }))

    async def disconnect(self, close_code):
        if hasattr(self, 'driver_id'):
            # Remove from groups
            await self.channel_layer.group_discard(self.driver_group, self.channel_name)
            await self.channel_layer.group_discard('online_drivers', self.channel_name)
            # Remove from Redis geo index
            await self._remove_driver_location()
            logger.info(f"Driver {self.driver_id} disconnected")

    async def receive(self, text_data):
        """
        Receive location update from driver.
        Expected: {"lng": float, "lat": float}
        """
        try:
            data = json.loads(text_data)
            lng = data.get('lng')
            lat = data.get('lat')

            if lng is None or lat is None:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'lng and lat are required'
                }))
                return

            # Update location in Redis Geo
            result = await self._update_driver_location(lng, lat)

            if result.get('success'):
                await self.send(text_data=json.dumps({
                    'type': 'location_updated',
                    'lng': lng,
                    'lat': lat,
                }))
            else:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': result.get('error', 'Failed to update location')
                }))

        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON'
            }))
        except Exception as e:
            logger.error(f"Error in DriverLocationConsumer.receive: {str(e)}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Internal server error'
            }))

    # -- Event handlers (called via channel layer) --

    async def ride_request(self, event):
        """Send incoming ride request notification to this driver."""
        await self.send(text_data=json.dumps({
            'type': 'ride_request',
            'trip_id': event['trip_id'],
            'rider_name': event.get('rider_name', ''),
            'pickup_lat': event['pickup_lat'],
            'pickup_lng': event['pickup_lng'],
            'destination_lat': event['destination_lat'],
            'destination_lng': event['destination_lng'],
            'pickup_address': event.get('pickup_address', ''),
            'destination_address': event.get('destination_address', ''),
            'estimated_fare': event.get('estimated_fare', ''),
        }))

    # -- Database helpers --

    @database_sync_to_async
    def _get_driver(self):
        try:
            return self.user.driver
        except Exception:
            return None

    @database_sync_to_async
    def _update_driver_location(self, lng, lat):
        from servers.redis import add_driver_location
        return add_driver_location(self.driver_id, lng=lng, lat=lat)

    @database_sync_to_async
    def _remove_driver_location(self):
        from servers.redis import remove_driver
        return remove_driver(self.driver_id)


class RideRequestConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for riders to request rides and receive updates.
    
    Connect: ws://host/ws/ride/request/?token=<jwt>
    Send:    {
        "pickup_lat": 17.385, "pickup_lng": 78.486,
        "destination_lat": 17.440, "destination_lng": 78.348,
        "pickup_address": "...", "destination_address": "..."
    }
    """

    async def connect(self):
        self.user = self.scope.get('user', AnonymousUser())

        if isinstance(self.user, AnonymousUser) or not self.user.is_authenticated:
            await self.close(code=4001)
            return

        self.rider_group = f'rider_{self.user.id}'

        # Join rider's personal group (for receiving trip updates)
        await self.channel_layer.group_add(self.rider_group, self.channel_name)

        await self.accept()
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': 'Rider connected, ready for ride requests',
        }))

    async def disconnect(self, close_code):
        if hasattr(self, 'rider_group'):
            await self.channel_layer.group_discard(self.rider_group, self.channel_name)

    async def receive(self, text_data):
        """
        Receive messages from rider.
        New request: {"pickup_lat": ..., "pickup_lng": ..., "destination_lat": ..., "destination_lng": ...}
        Retry:       {"action": "retry", "trip_id": <id>, "radius": <optional, meters>}
        """
        try:
            data = json.loads(text_data)
            action = data.get('action', 'request')

            if action == 'retry':
                await self._handle_retry(data)
                return

            # --- New ride request flow ---
            pickup_lat = data.get('pickup_lat')
            pickup_lng = data.get('pickup_lng')
            destination_lat = data.get('destination_lat')
            destination_lng = data.get('destination_lng')
            pickup_address = data.get('pickup_address', '')
            destination_address = data.get('destination_address', '')
            distance_km = data.get('distance_km')
            duration_min = data.get('duration_min')
            vehicle_type = data.get('vehicle_type')

            # Validate required fields
            if not all([pickup_lat, pickup_lng, destination_lat, destination_lng]):
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'pickup_lat, pickup_lng, destination_lat, destination_lng are required'
                }))
                return

            # Create trip in database
            trip = await self._create_trip(
                pickup_lat=pickup_lat,
                pickup_lng=pickup_lng,
                destination_lat=destination_lat,
                destination_lng=destination_lng,
                pickup_address=pickup_address,
                destination_address=destination_address,
                distance_km=distance_km,
                duration_min=duration_min,
                vehicle_type=vehicle_type,
            )

            if not trip:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Failed to create trip'
                }))
                return

            # Confirm trip creation to rider
            await self.send(text_data=json.dumps({
                'type': 'trip_created',
                'trip_id': trip.id,
                'estimated_fare': str(trip.estimated_fare) if trip.estimated_fare else None,
                'message': 'Searching for nearby drivers...'
            }))

            # Log ride request to Redis Stream (for future analytics, not driver notification)
            await self._publish_ride_request(trip)

            # Find and notify nearby drivers via WebSocket
            notified_count = await self._notify_nearby_drivers(
                trip=trip,
                pickup_lng=float(pickup_lng),
                pickup_lat=float(pickup_lat),
                destination_lat=destination_lat,
                destination_lng=destination_lng,
                pickup_address=pickup_address,
                destination_address=destination_address,
            )

            if notified_count > 0:
                await self.send(text_data=json.dumps({
                    'type': 'drivers_notified',
                    'trip_id': trip.id,
                    'drivers_notified': notified_count,
                    'message': f'{notified_count} nearby driver(s) notified'
                }))

        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON'
            }))
        except Exception as e:
            logger.error(f"Error in RideRequestConsumer.receive: {str(e)}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Internal server error'
            }))

    # -- Retry & shared helpers --

    async def _handle_retry(self, data):
        """
        Retry notifying nearby drivers for an existing pending trip.
        Expected: {"action": "retry", "trip_id": int, "radius": int (optional, meters)}
        """
        trip_id = data.get('trip_id')
        radius = data.get('radius', 5000)

        if not trip_id:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'trip_id is required for retry'
            }))
            return

        trip = await self._get_pending_trip(trip_id)
        if not trip:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Trip not found or already accepted by a driver'
            }))
            return

        await self.send(text_data=json.dumps({
            'type': 'retry_started',
            'trip_id': trip.id,
            'radius': radius,
            'message': 'Retrying — searching for nearby drivers...'
        }))

        notified_count = await self._notify_nearby_drivers(
            trip=trip,
            pickup_lng=float(trip.pickup_long),
            pickup_lat=float(trip.pickup_lat),
            destination_lat=float(trip.destination_lat),
            destination_lng=float(trip.destination_long),
            pickup_address=trip.pickup_address or '',
            destination_address=trip.destination_address or '',
            radius=radius,
        )

        if notified_count > 0:
            await self.send(text_data=json.dumps({
                'type': 'drivers_notified',
                'trip_id': trip.id,
                'drivers_notified': notified_count,
                'message': f'Retry: {notified_count} nearby driver(s) notified'
            }))

    async def _notify_nearby_drivers(self, trip, pickup_lng, pickup_lat,
                                      destination_lat, destination_lng,
                                      pickup_address, destination_address,
                                      radius=5000):
        """
        Find nearby drivers and send them a ride request via WebSocket.
        Returns the number of drivers notified.
        """
        nearby = await self._find_nearby_drivers(pickup_lng, pickup_lat, radius=radius)

        if not nearby:
            await self.send(text_data=json.dumps({
                'type': 'no_drivers',
                'trip_id': trip.id,
                'message': 'No nearby drivers found. Please try again shortly.'
            }))
            return 0

        rider_name = await self._get_rider_name()
        notified_count = 0
        for driver_info in nearby:
            driver_key = driver_info[0] if isinstance(driver_info, (list, tuple)) else driver_info
            if isinstance(driver_key, str) and driver_key.startswith('driver:'):
                driver_id = driver_key.split(':')[1]
                driver_group = f'driver_{driver_id}'
                await self.channel_layer.group_send(driver_group, {
                    'type': 'ride_request',
                    'trip_id': trip.id,
                    'rider_name': rider_name,
                    'pickup_lat': str(pickup_lat),
                    'pickup_lng': str(pickup_lng),
                    'destination_lat': str(destination_lat),
                    'destination_lng': str(destination_lng),
                    'pickup_address': pickup_address,
                    'destination_address': destination_address,
                    'estimated_fare': str(trip.estimated_fare) if trip.estimated_fare else '',
                })
                notified_count += 1

        return notified_count

    # -- Event handlers --

    async def trip_update(self, event):
        """Send trip status update to rider."""
        await self.send(text_data=json.dumps({
            'type': 'trip_update',
            'trip_id': event['trip_id'],
            'status': event['status'],
            'message': event.get('message', ''),
            'driver_id': event.get('driver_id'),
            'driver_name': event.get('driver_name', ''),
        }))

    # -- Database helpers --

    @database_sync_to_async
    def _create_trip(self, pickup_lat, pickup_lng, destination_lat, destination_lng,
                     pickup_address, destination_address,
                     distance_km=None, duration_min=None, vehicle_type=None):
        from decimal import Decimal
        from servers.ride.models import Trip, FarePricing
        from servers.ride.utils import estimate_amount
        from django.db import transaction

        try:
            # Parse distance and duration
            try:
                dist = float(distance_km) if distance_km is not None else 0
                dur = float(duration_min) if duration_min is not None else 0
            except (ValueError, TypeError):
                dist, dur = 0, 0

            fare = estimate_amount(dist, dur, vehicle_type=vehicle_type)

            with transaction.atomic():
                trip = Trip.objects.create(
                    user_id=self.user,
                    pickup_lat=pickup_lat,
                    pickup_long=pickup_lng,
                    destination_lat=destination_lat,
                    destination_long=destination_lng,
                    pickup_address=pickup_address,
                    destination_address=destination_address,
                    estimated_fare=fare['total_fare'],
                    estimated_distance_km=Decimal(str(dist)) if dist else None,
                    surge_multiplier=fare['surge_multiplier'],
                )

                FarePricing.objects.create(
                    trip_id=trip,
                    base_fare=fare['base_fare'],
                    distance_fare=fare['distance_fare'],
                    time_fare=fare['time_fare'],
                    surge_multiplier=fare['surge_multiplier'],
                    total_fare=fare['total_fare'],
                )

            # Schedule auto-cancel task
            from servers.ride.tasks import auto_cancel_trip
            from django.conf import settings
            auto_cancel_trip.apply_async((trip.id,), countdown=settings.TRIP_ACCEPT_TIMEOUT_SECONDS)

            return trip
        except Exception as e:
            logger.error(f"Failed to create trip: {str(e)}")
            return None

    @database_sync_to_async
    def _find_nearby_drivers(self, lng, lat, radius=5000, count=10):
        from servers.redis import nearby_drivers
        return nearby_drivers(lng=lng, lat=lat, radius=radius, count=count)

    @database_sync_to_async
    def _publish_ride_request(self, trip):
        from servers.redis import publish_ride_request
        return publish_ride_request(
            ride_id=trip.id,
            rider_id=self.user.id,
            pickup_lng=float(trip.pickup_long),
            pickup_lat=float(trip.pickup_lat),
            destination_lng=float(trip.destination_long),
            destination_lat=float(trip.destination_lat),
        )

    @database_sync_to_async
    def _get_rider_name(self):
        try:
            return self.user.full_name or self.user.phone_number
        except Exception:
            return ''

    @database_sync_to_async
    def _get_pending_trip(self, trip_id):
        """Get a trip only if it belongs to this rider and has no driver assigned yet."""
        from servers.ride.models import Trip
        try:
            trip = Trip.objects.get(id=trip_id, user_id=self.user)
            if trip.driver_id is not None:
                return None
            return trip
        except Trip.DoesNotExist:
            return None


class TripStatusConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time trip status updates.
    Both rider and driver join a trip-specific group.
    
    Connect: ws://host/ws/ride/trip/<trip_id>/?token=<jwt>
    Send (driver only):
        {"action": "accept"}
        {"action": "start"}
        {"action": "complete"}
        {"action": "cancel"}
    """

    async def connect(self):
        self.user = self.scope.get('user', AnonymousUser())

        if isinstance(self.user, AnonymousUser) or not self.user.is_authenticated:
            await self.close(code=4001)
            return

        self.trip_id = self.scope['url_route']['kwargs']['trip_id']
        self.trip_group = f'trip_{self.trip_id}'

        # Verify user is part of this trip
        is_participant = await self._is_trip_participant()
        if not is_participant:
            await self.close(code=4003)
            return

        await self.channel_layer.group_add(self.trip_group, self.channel_name)

        await self.accept()
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'trip_id': self.trip_id,
            'message': 'Connected to trip updates',
        }))

    async def disconnect(self, close_code):
        if hasattr(self, 'trip_group'):
            await self.channel_layer.group_discard(self.trip_group, self.channel_name)

    async def receive(self, text_data):
        """
        Receive trip actions from driver.
        Expected: {"action": "accept|start|complete|cancel"}
        """
        try:
            data = json.loads(text_data)
            action = data.get('action')

            if action not in ('accept', 'start', 'complete', 'cancel'):
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Invalid action. Must be: accept, start, complete, or cancel'
                }))
                return

            # Check if user is the driver for this trip (or accepting driver)
            is_driver = await self._is_driver()

            if action == 'accept':
                if not is_driver:
                    await self.send(text_data=json.dumps({
                        'type': 'error',
                        'message': 'Only drivers can accept rides'
                    }))
                    return
                result = await self._accept_trip()
            elif action == 'start':
                if not is_driver:
                    await self.send(text_data=json.dumps({
                        'type': 'error',
                        'message': 'Only drivers can start rides'
                    }))
                    return
                result = await self._update_trip_status('in_progress')
            elif action == 'complete':
                if not is_driver:
                    await self.send(text_data=json.dumps({
                        'type': 'error',
                        'message': 'Only drivers can complete rides'
                    }))
                    return
                result = await self._update_trip_status('completed')
            elif action == 'cancel':
                result = await self._update_trip_status('cancelled')

            if result.get('success'):
                # Broadcast status to all participants in the trip group
                await self.channel_layer.group_send(self.trip_group, {
                    'type': 'trip_status_update',
                    'trip_id': self.trip_id,
                    'status': action,
                    'message': result.get('message', ''),
                    'driver_id': result.get('driver_id'),
                })

                # Also notify the rider via their personal group
                rider_id = result.get('rider_id')
                if rider_id:
                    await self.channel_layer.group_send(f'rider_{rider_id}', {
                        'type': 'trip_update',
                        'trip_id': self.trip_id,
                        'status': action,
                        'message': result.get('message', ''),
                        'driver_id': result.get('driver_id'),
                        'driver_name': result.get('driver_name', ''),
                    })
            else:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': result.get('error', 'Action failed')
                }))

        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON'
            }))
        except Exception as e:
            logger.error(f"Error in TripStatusConsumer.receive: {str(e)}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Internal server error'
            }))

    # -- Event handlers --

    async def trip_status_update(self, event):
        """Broadcast trip status to all participants."""
        await self.send(text_data=json.dumps({
            'type': 'trip_status_update',
            'trip_id': event['trip_id'],
            'status': event['status'],
            'message': event.get('message', ''),
            'driver_id': event.get('driver_id'),
        }))

    # -- Database helpers --

    @database_sync_to_async
    def _is_trip_participant(self):
        from servers.ride.models import Trip
        try:
            trip = Trip.objects.get(id=self.trip_id)
            # Rider check
            if trip.user_id_id == self.user.id:
                return True
            # Driver check
            if trip.driver_id and hasattr(self.user, 'driver'):
                return trip.driver_id_id == self.user.driver.id
            # Allow any driver to join if no driver assigned yet (for accepting)
            if not trip.driver_id and hasattr(self.user, 'driver'):
                return True
            return False
        except Trip.DoesNotExist:
            return False

    @database_sync_to_async
    def _is_driver(self):
        try:
            return hasattr(self.user, 'driver') and self.user.driver is not None
        except Exception:
            return False

    @database_sync_to_async
    def _accept_trip(self):
        from servers.ride.models import Trip, TripStatus
        from django.utils import timezone

        try:
            trip = Trip.objects.get(id=self.trip_id)

            # Check if already accepted
            if trip.driver_id is not None:
                return {'success': False, 'error': 'Trip already accepted by another driver'}

            driver = self.user.driver
            status_obj, _ = TripStatus.objects.get_or_create(
                status_code='accepted',
                defaults={'description': 'Trip accepted by driver'}
            )

            trip.driver_id = driver
            trip.status_id = status_obj
            trip.accepted_at = timezone.now()
            trip.save()

            # Create notification for rider
            from servers.rider.models import Notification
            Notification.objects.create(
                user_id=trip.user_id,
                title='Ride Accepted',
                message=f'Driver {driver.user_id.full_name} has accepted your ride.',
            )

            return {
                'success': True,
                'message': 'Trip accepted',
                'driver_id': driver.id,
                'driver_name': str(driver),
                'rider_id': trip.user_id_id,
            }
        except Trip.DoesNotExist:
            return {'success': False, 'error': 'Trip not found'}
        except Exception as e:
            logger.error(f"Error accepting trip: {str(e)}")
            return {'success': False, 'error': str(e)}

    @database_sync_to_async
    def _update_trip_status(self, status_code):
        from servers.ride.models import Trip, TripStatus
        from django.utils import timezone

        try:
            trip = Trip.objects.get(id=self.trip_id)
            status_obj, _ = TripStatus.objects.get_or_create(
                status_code=status_code,
                defaults={'description': f'Trip {status_code}'}
            )

            trip.status_id = status_obj

            # Set timestamps based on status
            if status_code == 'in_progress':
                trip.started_at = timezone.now()
            elif status_code == 'completed':
                trip.completed_at = timezone.now()
                # Create payment on trip completion
                self._create_payment_on_complete(trip)
                # Create driver earning
                self._create_driver_earning(trip)
                
                from servers.rider.models import Notification
                Notification.objects.create(
                    user_id=trip.user_id,
                    title='Ride Completed',
                    message=f'Your ride has been completed. Final fare: ₹{trip.final_fare or trip.estimated_fare}',
                )
            elif status_code == 'cancelled':
                trip.cancelled_at = timezone.now()
                self._process_refund_on_cancel(trip)
                
                from servers.rider.models import Notification
                Notification.objects.create(
                    user_id=trip.user_id,
                    title='Ride Cancelled',
                    message=f'Your ride has been cancelled.',
                )

            trip.save()

            result = {
                'success': True,
                'message': f'Trip {status_code}',
                'driver_id': trip.driver_id_id if trip.driver_id else None,
                'rider_id': trip.user_id_id,
            }

            # Include payment info for completed trips
            if status_code == 'completed':
                payment = trip.payments.first()
                if payment:
                    result['payment'] = {
                        'payment_id': payment.id,
                        'amount': str(payment.amount),
                        'method': payment.method,
                        'status': payment.status,
                        'razorpay_order_id': payment.razorpay_order_id,
                    }

            return result
        except Trip.DoesNotExist:
            return {'success': False, 'error': 'Trip not found'}
        except Exception as e:
            logger.error(f"Error updating trip status: {str(e)}")
            return {'success': False, 'error': str(e)}

    def _create_payment_on_complete(self, trip):
        """Create a Payment record when trip is completed."""
        from servers.payments.models import Payment, TransactionHistory

        # Skip if payment already exists
        if trip.payments.exists():
            return

        amount = trip.final_fare or trip.estimated_fare
        if not amount:
            logger.warning(f"No fare amount for trip {trip.id}, skipping payment creation")
            return

        payment_method = trip.payment_method or 'cash'

        if payment_method == 'cash':
            # Cash payment — mark completed immediately
            Payment.objects.create(
                trip_id=trip,
                user_id=trip.user_id,
                amount=amount,
                method='cash',
                status='completed',
            )
            trip.payment_status = 'completed'

            # Create transaction history for cash
            if trip.driver_id:
                TransactionHistory.objects.create(
                    trip_id=trip,
                    user_id=trip.user_id,
                    driver_id=trip.driver_id,
                    amount=amount,
                    method='cash',
                    user_name=trip.user_id.full_name or trip.user_id.phone_number,
                    status='completed',
                )
        else:
            # Online payment — create pending payment with Razorpay order
            from servers.payments.razorpay_utils import create_razorpay_order

            order = create_razorpay_order(amount=amount, trip_id=trip.id)
            Payment.objects.create(
                trip_id=trip,
                user_id=trip.user_id,
                amount=amount,
                method='online',
                status='pending',
                razorpay_order_id=order['id'] if order else None,
            )
            trip.payment_status = 'pending'

    def _create_driver_earning(self, trip):
        """Calculate and create DriverEarning record."""
        from servers.driver.models import DriverEarning
        from django.conf import settings
        from decimal import Decimal

        if not trip.driver_id:
            return

        amount = trip.final_fare or trip.estimated_fare or Decimal('0.00')
        commission_rate = getattr(settings, 'PLATFORM_COMMISSION_PERCENT', 20)
        
        commission = (amount * Decimal(commission_rate)) / Decimal(100)
        net_amount = amount - commission

        DriverEarning.objects.create(
            driver_id=trip.driver_id,
            trip_id=trip,
            amount=amount,
            commission=commission,
            net_amount=net_amount,
        )

    def _process_refund_on_cancel(self, trip):
        """Process refund if payment was completed online."""
        from servers.payments.models import Payment
        from servers.payments.razorpay_utils import create_refund
        from servers.rider.models import Notification

        payment = Payment.objects.filter(trip_id=trip, method='online', status='completed').first()
        if payment and payment.razorpay_payment_id:
            refund = create_refund(payment.razorpay_payment_id)
            if refund:
                payment.status = 'refunded'
                payment.save()
                
                trip.payment_status = 'refunded'
                trip.save(update_fields=['payment_status'])
                
                Notification.objects.create(
                    user_id=trip.user_id,
                    title='Refund Processed',
                    message=f'Your refund of ₹{payment.amount} has been initiated due to cancellation.',
                )

