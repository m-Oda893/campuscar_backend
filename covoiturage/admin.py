from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Utilisateur, Trajet, Reservation, Voiture, ProfilChauffeur

admin.site.register(Trajet)
admin.site.register(Reservation)
admin.site.register(Voiture)



@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):
    list_display = (
        'username', 'first_name', 'last_name', 'email',
        'identifiant', 'est_personnel', 'is_staff',
    )
    search_fields = ('username', 'first_name', 'last_name', 'email', 'identifiant')

    fieldsets = UserAdmin.fieldsets + (
        ('Infos CampusCar', {
            'fields': ('telephone', 'date_naissance', 'est_personnel',
                       'identifiant', 'photo', 'note'),
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Infos CampusCar', {
            'fields': ('email', 'telephone', 'date_naissance',
                       'est_personnel', 'identifiant'),
        }),
    )

@admin.register(ProfilChauffeur)
class ProfilChauffeurAdmin(admin.ModelAdmin):
    list_display = ('utilisateur', 'numero_permis', 'verifie', 'cree_le')
    list_editable = ('verifie',)   # on coche directement dans la liste