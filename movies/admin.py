from django.contrib import admin
from .models import Movie, Theater, Seat, Booking, Genre, Language

@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ['name']

@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ['name']

@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display = ['name', 'rating', 'cast', 'description']
    filter_horizontal = ['genres', 'languages']

@admin.register(Theater)
class TheaterAdmin(admin.ModelAdmin):
    list_display = ['name', 'movie', 'time']

@admin.register(Seat)
class SeatAdmin(admin.ModelAdmin):
    list_display = ['theater', 'seat_number', 'is_booked']

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['user', 'seat', 'movie','theater','booked_at']
