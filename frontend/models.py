# Copyright (C) 2016 Seva Ivanov
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>

"""
    unique constraints are used because multiple primary keys aren't supported.
    import_export:
        import:
            using primary_key will create KeyError: u'id'.
            w/o null=True -> 'NOT NULL constraint failed' on empty fields.
"""

import pyexiv2
import os, shutil, imghdr
from datetime import date

from kedfilms import utils

from django.db import models
from django.contrib import admin
from django.conf import settings
from django.core.exceptions import ValidationError

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
MEDIA_URL = settings.MEDIA_URL
IMAGES_ROOT = os.path.join(settings.MEDIA_ROOT, "images")
IMAGES_DIRNAME = "original"
THUMBNAILS_DIRNAMES = ['x200', 'x800']

# offline uploads only, hence, no media/ used.
def get_photo_upload_to_by_category(instance, filename):
    return os.path.join("images", instance.category.name, "original", filename)

class Author(models.Model):
    name = models.CharField(
        unique = True,
        max_length = 50,
        default = "Unknown"
    )

    def __unicode__(self):
        return self.name

class Category(models.Model):
    name = models.CharField(
        unique = True,
        max_length = 50,
    )
    context = models.CharField(
        max_length = 50
    )
    folder = models.CharField(
        max_length = 50,
        blank = True,
        default = None,
        null=True
    )

    def __unicode__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Categories"

class Photo(models.Model):
    author = models.ForeignKey("Author")
    category = models.ForeignKey(
        "Category",
        limit_choices_to={"context": "Photo"}
    )
    cached_category = models.ForeignKey(
        "Category",
        related_name="cached_category",
        limit_choices_to={"context": "Photo"}
    )
    hardware = models.ForeignKey(
        "Category",
        related_name="hardware",
        limit_choices_to={"context": "Hardware"},
        null = True
    )
    application = models.ForeignKey(
        "Category",
        related_name="application",
        limit_choices_to={"context": "Software"},
        null = True
    )

    image = models.ImageField(
        upload_to = get_photo_upload_to_by_category
    )
    cached_image_path = models.CharField(
        max_length = 200,
        unique = True,
        blank = True
    )
    fragment_identifier = models.CharField(
        max_length = 41,
        unique = True
    )
    title = models.CharField(
        max_length = 50
    )
    date_created = models.DateField(
        default = date.today
    )

    def get_image_url(self):
        return os.path.join(MEDIA_URL, "images", self.category.name, IMAGES_DIRNAME, 
            os.path.basename(str(self.image))
        )

    def get_image_thumbnails_urls(self):
        urls = {}
        for dirname in THUMBNAILS_DIRNAMES:
            urls[dirname] = os.path.join(MEDIA_URL, "images", self.category.name, 
                dirname, os.path.basename(str(self.image))
            )
        return urls

    def get_image_abspath(self):
        return os.path.join(IMAGES_ROOT, self.category.name, IMAGES_DIRNAME, 
            os.path.basename(str(self.image))
        )

    @property
    def get_image_type(self):
        return imghdr.what(self.get_image_abspath())

    def get_thumbnails_abspaths(self):
        filename = os.path.basename(self.cached_image_path)
        thumbnails_abspaths = []

        for dirname in THUMBNAILS_DIRNAMES:
            thumbnail_path = os.path.join(IMAGES_ROOT, self.category.name, dirname, filename)
            thumbnails_abspaths.append(thumbnail_path)

        return thumbnails_abspaths

    # convert is part of ImageMagick
    def generate_thumbnails(self, is_gif=False):
        filename = os.path.basename(self.cached_image_path)
        source = self.cached_image_path

        for dirname in THUMBNAILS_DIRNAMES:
            new_size = dirname
            thumbnail_path = os.path.join(IMAGES_ROOT, self.category.name, dirname)

            if os.path.exists(thumbnail_path) == False:
                os.makedirs(thumbnail_path)

            if is_gif and dirname != 'x200':
                continue
            elif is_gif:
                target = os.path.join(thumbnail_path, "temporary-" + filename)
                os.system("convert " + source + " -coalesce " + target)
                source = target
            
            target = os.path.join(thumbnail_path, filename)
            os.system("convert " + source + " -resize " + new_size + " " + target)

            if is_gif and os.path.exists(source):
                os.remove(source)

    def move_image_to_updated_category(self):
        filename = os.path.basename(self.cached_image_path)
        subdirectories = THUMBNAILS_DIRNAMES + [IMAGES_DIRNAME]

        for subdirectory in subdirectories:
            current_image_path = os.path.join(IMAGES_ROOT,
                self.cached_category.name, subdirectory, filename
            )
            new_image_path = os.path.join(IMAGES_ROOT, 
                self.category.name, subdirectory, filename
            )
            # destination has this file
            if os.path.isfile(new_image_path):
                raise ValidationError("Can't change the image category: Same image filename exists.")

            shutil.move(current_image_path, new_image_path)

    def delete_image(self):
        if os.path.exists(self.cached_image_path):
            os.remove(self.cached_image_path)

    def delete_thumbnails(self):
        filename = os.path.basename(self.cached_image_path)

        for dirname in THUMBNAILS_DIRNAMES:
            thumbnail_path = os.path.join(IMAGES_ROOT, self.category.name, dirname)
            if os.path.exists(thumbnail_path):
                shutil.rmtree(thumbnail_path)

    # overwritten method
    def delete(self, *args, **kwargs):
        super(Photo, self).delete(*args, **kwargs)
        self.delete_image()
        self.delete_thumbnails()

    def __unicode__(self):
        return self.title

    class Meta:
        unique_together = (
            ('category', 'fragment_identifier')
        )

class Video(models.Model):
    INTRO = 'intro'
    FAVORITE = 'favorite'
    EVENT = 'event'
    DANCER = 'dancer'

    CATEGORIES = (
        (INTRO, 'Brief introductory passage'),
        (FAVORITE, 'Personal Favorites'),
        (EVENT, 'A Gathering Of People'),
        (DANCER, 'Physical Expression'),
    )

    category = models.CharField(
        max_length = 2,
        choices = CATEGORIES
    )
    date_created = models.DateField(
        default = date.today,
        blank = False
    )
    # blank = video locally hosted
    iframe_src = models.CharField(
        max_length = 250,
        unique = True,
        blank = True
    )
    # locally hosted video information
    filename = models.CharField(
        max_length = 250
    )
    posterfile = models.CharField(
        max_length = 250 
    )
    title = models.CharField(
        max_length = 50
    )
    author = models.CharField(
        max_length = 50
    )
    description = models.CharField(
        max_length = 50 
    )
    hardware = models.CharField(
        max_length = 50
    )
    application = models.CharField(
        max_length = 50
    )

class Skill(models.Model):
    GN = "general"
    MD = 'methods of development'
    OS = 'operative system'
    FR = 'framework'
    RC = 'revision control'
    PR = 'programming'
    ML = 'markup language'
    DB = 'database'
    SR = 'server'
    SW = 'sofrware'
    HW = 'hardware'
    VA = 'visual art'

    title = models.CharField(
        max_length = 10
    )
    description = models.CharField(
        max_length = 255
    )
    category = models.CharField(
        max_length = 2,
        default = GN
    )
    rating_on_five = models.DecimalField(
        max_digits = 1,
        decimal_places = 0
    )
    
    class Meta:
        unique_together = (
            ('category', 'title')
        )

class Project(models.Model):

    TIMELINE = {
        "2015-10":
        {
            "title": "Lindenmayer System",
            "description": """An interactive web experience for the exploration 
                of the L-Systems. Inspired by the book The Algorithmic Beauty of 
                Plants written by Przemyslaw Prusinkiewicz and Aristid Lindenmayer.
            """,
            "url": "https://sevaivanov.github.io/lindenmayer/"
        },
        "2015-9":
        {
            "title": "3D Cube",
            "description": """A 3D Cube made of html / css  that was designed for
                Computation Arts as the main projects entry. Unfortunately, cross-browsers
                compatibility issues made me reconsider my choice.
            """,
            "url": "/cart/3Dcube/3Dcube/"
        },
        "2015-7":
        {
            "title": "Tcp Viewer",
            "description": """We wrap tcpflow in the backend to arrange data for 
            dynamic visualisation for the frontend. Our goal is to raise awareness 
            about the quantity of personal information available to everyone connected 
            to a network.
            """,
            "url": "https://github.com/sevaivanov/tcpviewer#tcp-viewer"
        },
        "2014-12":
        {
            "title": "Personal Website",
            "description": """I built it to centralize my realizations and gain 
                web development experience. I challenged myself to only use CSS3 
                & HTML5 and leave JavaScript aside. It is using the Django Python 
                Web framework to build static web pages.
            """,
            "url": "https://github.com/sevaivanov/personal-website#personal-website"
        },
        "2013-12":
        {
            "title": "Distributed Connect4",
            "description": """This is a distributed LipeRMI Connect4 game. 
            It is built under the MVC design pattern. The server contains 
            the game database and defines the rules. The clients connect 
            to the server in order to play or watch an ongoing game.
            """,
            "url": "https://github.com/sevaivanov/connect4#distributed-connect4"
        }
    }
