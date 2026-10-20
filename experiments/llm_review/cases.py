"""Pages and planted cases for the LLM second pass experiment.

The fictional site is Quartier Belvedere, a neighbourhood shopping guide. It
uses four middle ground terms that the rules cannot judge alone:

  mail     email (anglicism, use courriel) or a shopping centre or promenade
  chat     online chat (anglicism, use clavardage) or a cat
  booking  a reservation (anglicism, use reservation) or the Booking.com brand
  spam     junk email (anglicism, use pourriel) or the Spam canned meat brand

Each case is one paragraph with exactly one of these terms. Everything else
on the pages is meant to be clean Quebec French, so any other finding counts
as a false positive.

label "flag" means a Quebec French editor would replace the term.
label "ok" means the term is correct as written.
"""

from __future__ import annotations

SITE_NAME = "Quartier Belvédère"

# (case id, term, label, paragraph, why)
PAGES = {
    "accueil": {
        "title": "Quartier Belvédère | Magasiner au cœur de la ville",
        "blocks": [
            ("h1", "Bienvenue dans le Quartier Belvédère"),
            ("p", "Le quartier réunit des commerces de proximité, des cafés et des services pour toute la famille."),
            ("case", "C01", "mail", "ok", "Le Mail des Érables ouvre ses portes à 9 h du lundi au samedi.", "Name of a shopping centre"),
            ("case", "C02", "mail", "ok", "Plus de 80 boutiques vous attendent au mail, à deux pas du métro.", "Refers to the shopping centre"),
            ("p", "Le stationnement est gratuit les fins de semaine."),
            ("case", "C03", "booking", "ok", "Vous voyagez? Nos hôtels partenaires sont aussi offerts sur Booking.com.", "Brand name"),
            ("case", "C04", "chat", "ok", "Ne manquez pas Pistache, le chat de la librairie, qui dort dans la vitrine tout l'après-midi.", "A cat"),
            ("p", "Abonnez-vous à notre infolettre pour connaître les événements à venir."),
            ("p", "Le Quartier Belvédère s'étend sur six rues, entre le parc du Ruisseau et la gare."),
            ("p", "Chaque été, la rue des Pins devient piétonne et accueille des spectacles gratuits."),
            ("p", "Des supports à vélos sont installés devant la plupart des commerces."),
            ("p", "Consultez le calendrier pour connaître les heures d'ouverture pendant les jours fériés."),
            ("case", "C05", "chat", "flag", "Une question? Ouvrez le chat en bas de la page pour joindre notre équipe.", "Online chat, use clavardage"),
        ],
    },
    "contact": {
        "title": "Nous joindre | Quartier Belvédère",
        "blocks": [
            ("h1", "Nous joindre"),
            ("p", "Notre bureau d'accueil est situé au 120, rue des Pins."),
            ("case", "C06", "mail", "flag", "Écrivez-nous par mail et nous vous répondrons sous 48 heures.", "Email, use courriel"),
            ("case", "C07", "mail", "flag", "Vous recevrez un mail de confirmation après l'envoi du formulaire.", "Email, use courriel"),
            ("case", "C08", "chat", "flag", "Notre chat en ligne est ouvert de 9 h à 17 h en semaine.", "Online chat, use clavardage"),
            ("case", "C09", "chat", "flag", "Les conseillers répondent par chat ou par téléphone.", "Online chat, use clavardage"),
            ("case", "C10", "spam", "flag", "Si vous ne voyez pas notre réponse, vérifiez votre dossier spam.", "Junk email, use pourriel"),
            ("p", "Vous pouvez aussi nous écrire par courriel à info@quartier-belvedere.example."),
            ("p", "Pour signaler un problème sur la voie publique, communiquez directement avec la Ville."),
            ("p", "Les demandes des médias sont traitées par notre équipe des communications."),
            ("p", "Nous ne recueillons que les renseignements nécessaires pour répondre à votre demande."),
        ],
    },
    "boutiques": {
        "title": "Boutiques et services | Quartier Belvédère",
        "blocks": [
            ("h1", "Boutiques et services"),
            ("p", "Découvrez les commerçants du quartier, de la mode à l'alimentation."),
            ("case", "C11", "mail", "ok", "La boutique Lune et Laine se trouve au deuxième étage du mail.", "Refers to the shopping centre"),
            ("case", "C12", "mail", "ok", "Le mail piétonnier de la rue des Pins accueille un marché public tous les samedis.", "A pedestrian promenade"),
            ("case", "C13", "chat", "ok", "L'Animalerie du Coin offre de la nourriture pour chats et chiens.", "Cats"),
            ("case", "C14", "chat", "ok", "Le refuge organise une journée d'adoption : venez rencontrer un chat qui cherche une famille.", "A cat"),
            ("case", "C15", "spam", "ok", "Au casse-croûte Chez Lola, essayez le sandwich hawaïen au Spam et à l'ananas.", "Brand of canned meat"),
            ("case", "C16", "spam", "ok", "Le menu du midi propose aussi des bouchées de Spam grillé.", "Brand of canned meat"),
            ("p", "La plupart des boutiques sont ouvertes jusqu'à 21 h le jeudi et le vendredi."),
            ("p", "Vous trouverez aussi une quincaillerie, deux pharmacies et une épicerie fine."),
            ("p", "Plusieurs commerçants acceptent les cartes-cadeaux du quartier."),
            ("p", "La fromagerie offre des dégustations gratuites le samedi matin."),
        ],
    },
    "hebergement": {
        "title": "Hébergement | Quartier Belvédère",
        "blocks": [
            ("h1", "Où dormir dans le quartier"),
            ("p", "L'Auberge du Belvédère propose 24 chambres à quelques minutes des boutiques."),
            ("case", "C17", "booking", "flag", "Faites votre booking en ligne en quelques clics.", "A reservation, use réservation"),
            ("case", "C18", "booking", "flag", "Confirmez votre booking au moins 48 heures avant votre arrivée.", "A reservation, use réservation"),
            ("case", "C19", "booking", "flag", "Le booking des salles de réunion se fait uniquement par téléphone.", "A reservation, use réservation"),
            ("case", "C20", "booking", "ok", "L'Auberge du Belvédère est aussi présente sur Booking et Airbnb.", "Brand name"),
            ("case", "C21", "booking", "ok", "Selon les avis publiés sur Booking.com, nos chambres sont parmi les plus calmes du quartier.", "Brand name"),
            ("p", "Le déjeuner est servi de 7 h à 10 h dans la salle à manger."),
            ("p", "Toutes les chambres ont une salle de bain privée et l'accès gratuit à Internet sans fil."),
            ("p", "L'arrivée se fait à partir de 15 h et le départ, avant 11 h."),
            ("p", "Le stationnement de l'auberge est réservé à la clientèle."),
        ],
    },
    "emplois": {
        "title": "Emplois | Quartier Belvédère",
        "blocks": [
            ("h1", "Travailler dans le quartier"),
            ("p", "Les commerces du quartier recrutent toute l'année, à temps plein ou à temps partiel."),
            ("case", "C22", "mail", "flag", "Envoyez votre CV par mail à l'adresse indiquée ci-dessous.", "Email, use courriel"),
            ("case", "C23", "mail", "flag", "Nous lisons chaque mail reçu et contactons les candidats retenus.", "Email, use courriel"),
            ("case", "C24", "chat", "flag", "Vous pouvez aussi poser vos questions à notre équipe des ressources humaines par chat.", "Online chat, use clavardage"),
            ("case", "C25", "chat", "ok", "Petite surprise : le chat du bureau, Moka, fait partie de l'équipe depuis 2019.", "A cat"),
            ("case", "C26", "spam", "flag", "Nous ne répondons pas aux messages publicitaires non sollicités, que nous classons comme spam.", "Junk email, use pourriel"),
            ("p", "Adresse pour les candidatures : emplois@quartier-belvedere.example."),
            ("p", "Les offres sont mises à jour chaque lundi."),
            ("p", "Plusieurs postes conviennent aux étudiants qui cherchent un emploi d'été."),
            ("p", "Les employeurs du quartier offrent souvent des horaires flexibles."),
        ],
    },
}


def cases() -> list[dict]:
    out = []
    for slug, page in PAGES.items():
        for block in page["blocks"]:
            if block[0] == "case":
                _, cid, term, label, text, why = block
                out.append({"id": cid, "page": slug, "term": term, "label": label, "text": text, "why": why})
    return out
