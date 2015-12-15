from django.db import models


class Order(models.Model):
    patient_name = models.CharField(
        max_length=255,
    )


class CreditCardTransaction(models.Model):
    cardholder_name = models.CharField(
        max_length=255,
    )
