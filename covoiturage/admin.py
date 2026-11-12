from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Paiement, Utilisateur, Trajet, Reservation, Voiture, ProfilChauffeur , Zone
from .models import Signalement
from .models import Notification, Avis
from .models import PointPassage


admin.site.register(Reservation)
admin.site.register(Voiture)
admin.site.register(PointPassage)


class PointPassageInline(admin.TabularInline):
    model = PointPassage
    extra = 0


fieldsets = UserAdmin.fieldsets + (
    ('CampusCar', {'fields': ('annulations_tardives',)}),
)


@admin.register(Trajet)
class TrajetAdmin(admin.ModelAdmin):
    inlines = [PointPassageInline]




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



@admin.register(Paiement)
class PaiementAdmin(admin.ModelAdmin):
    list_display = ('id_transaction', 'utilisateur', 'montant', 'plateforme', 'statut', 'date_heure' , 'type')
    list_filter = ('plateforme', 'statut' , 'type')
    readonly_fields = ('id_transaction', 'date_heure')



@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('destinataire', 'type', 'message', 'lue', 'cree_le')
    list_filter = ('type', 'lue')


@admin.register(Avis)
class AvisAdmin(admin.ModelAdmin):
    list_display = ('reservation', 'note', 'commentaire', 'cree_le')



