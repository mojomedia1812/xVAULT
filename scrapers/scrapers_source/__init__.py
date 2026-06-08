

from six import iteritems
import os.path
from .import de

scraper_source = os.path.dirname(__file__)
__all__ = [x[1] for x in os.walk(os.path.dirname(__file__))][0]

##--de--##
german_providers = de.__all__

##--All Providers--##
total_providers = {'de': german_providers}
all_providers = []
for key, value in iteritems(total_providers):
	all_providers += value
