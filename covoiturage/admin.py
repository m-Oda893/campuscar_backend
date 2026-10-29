from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Utilisateur, Trajet, Reservation, Voiture, ProfilChauffeur , Zone
from .models import Signalement

admin.site.register(Trajet)
admin.site.register(Reservation)
admin.site.register(Voiture)


fieldsets = UserAdmin.fieldsets + (
    ('CampusCar', {'fields': ('annulations_tardives',)}),
)

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



@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):
    list_display = ('nom', 'latitude', 'longitude')



@admin.register(Signalement)
class SignalementAdmin(admin.ModelAdmin):
    list_display = ('cible', 'auteur', 'motif', 'statut', 'cree_le')
    list_filter = ('statut', 'motif')
    list_editable = ('statut',)
    actions = ['suspendre_les_comptes_signales']

    @admin.action(description="Suspendre les comptes signalés")
    def suspendre_les_comptes_signales(self, request, queryset):
        for s in queryset.select_related('cible'):
            s.cible.is_active = False   # compte désactivé : connexion et token refusés
            s.cible.save(update_fields=['is_active'])
        queryset.update(statut='traite')