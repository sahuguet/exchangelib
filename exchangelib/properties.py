import abc
import base64
import logging

from six import text_type, string_types

from .ewsdatetime import EWSDateTime
from .services import MNS, TNS
from .util import add_xml_child, get_xml_attr, set_xml_value, create_element

string_type = string_types[0]
log = logging.getLogger(__name__)


class Choice(text_type):
    # A helper class used for string enums
    pass


class Email(text_type):
    # A helper class used for email address string
    pass


class AnyURI(text_type):
    # Helper to mark strings that must conform to xsd:anyURI
    # If we want an URI validator, see http://stackoverflow.com/questions/14466585/is-this-regex-correct-for-xsdanyuri
    pass


class Body(text_type):
    # Helper to mark the 'body' field as a complex attribute.
    # MSDN: https://msdn.microsoft.com/en-us/library/office/jj219983(v=exchg.150).aspx
    body_type = 'Text'


class HTMLBody(Body):
    # Helper to mark the 'body' field as a complex attribute.
    # MSDN: https://msdn.microsoft.com/en-us/library/office/jj219983(v=exchg.150).aspx
    body_type = 'HTML'


class Subject(text_type):
    # A helper class used for subject string
    MAXLENGTH = 255

    def clean(self):
        if len(self) > self.MAXLENGTH:
            raise ValueError("'%s' value '%s' exceeds length %s" % (self.__class__.__name__, self, self.MAXLENGTH))


class Location(text_type):
    # A helper class used for location string
    MAXLENGTH = 255

    def clean(self):
        if len(self) > self.MAXLENGTH:
            raise ValueError("'%s' value '%s' exceeds length %s" % (self.__class__.__name__, self, self.MAXLENGTH))


class Content(bytes):
    # Helper to work with the base64 encoded binary Attachment content field
    def b64encode(self):
        return base64.b64encode(self).decode('ascii')

    def b64decode(self):
        return base64.b64decode(self)


class MimeContent(text_type):
    # Helper to work with the base64 encoded MimeContent Message field
    def b64encode(self):
        return base64.b64encode(self).decode('ascii')

    def b64decode(self):
        return base64.b64decode(self)


class EWSElement(object):
    __metaclass__ = abc.ABCMeta

    ELEMENT_NAME = None
    FIELDS = tuple()
    NAMESPACE = TNS  # Either TNS or MNS

    __slots__ = tuple()

    @abc.abstractmethod
    def clean(self):
        # Perform any attribute validation here
        return

    @abc.abstractmethod
    def to_xml(self, version):
        raise NotImplementedError()

    @abc.abstractclassmethod
    def from_xml(cls, elem):
        raise NotImplementedError()

    @classmethod
    def request_tag(cls):
        return {
            TNS: 't:%s' % cls.ELEMENT_NAME,
            MNS: 'm:%s' % cls.ELEMENT_NAME,
        }[cls.NAMESPACE]

    @classmethod
    def response_tag(cls):
        return '{%s}%s' % (cls.NAMESPACE, cls.ELEMENT_NAME)

    @classmethod
    def get_field_by_fieldname(cls, fieldname):
        if not hasattr(cls, '_fields_map'):
            cls._fields_map = {f.name: f for f in cls.FIELDS}
        return cls._fields_map[fieldname]

    @classmethod
    def add_field(cls, field, idx):
        # Insert a new field at the preferred place in the tuple and invalidate the fieldname cache
        cls.FIELDS = cls.FIELDS[0:idx] + (field,) + cls.FIELDS[idx:]
        try:
            delattr(cls, '_fields_map')
        except AttributeError:
            pass

    @classmethod
    def remove_field(cls, field):
        # Remove the given field and invalidate the fieldname cache
        cls.FIELDS = tuple(f for f in cls.FIELDS if f != field)
        try:
            delattr(cls, '_fields_map')
        except AttributeError:
            pass

    def __eq__(self, other):
        return hash(self) == hash(other)

    def __hash__(self):
        return hash(tuple(getattr(self, f) for f in self.__slots__))

    def __repr__(self):
        return self.__class__.__name__ + repr(tuple(getattr(self, f) for f in self.__slots__))


class MessageHeader(EWSElement):
    # MSDN: https://msdn.microsoft.com/en-us/library/office/aa565307(v=exchg.150).aspx
    ELEMENT_NAME = 'InternetMessageHeader'
    NAME_ATTR = 'HeaderName'

    __slots__ = ('name', 'value')

    def __init__(self, name, value):
        self.name = name
        self.value = value

    def to_xml(self, version):
        self.clean()
        elem = create_element(self.request_tag())
        # Use .set() to not fill up the create_element() cache with unique values
        elem.set(self.NAME_ATTR, self.name)
        set_xml_value(elem, self.value, version)
        return elem

    @classmethod
    def from_xml(cls, elem):
        if elem is None:
            return None
        assert elem.tag == cls.response_tag(), (cls, elem.tag, cls.response_tag())
        res = cls(name=elem.get(cls.NAME_ATTR), value=elem.text)
        elem.clear()
        return res


class ItemId(EWSElement):
    # 'id' and 'changekey' are UUIDs generated by Exchange
    # MSDN: https://msdn.microsoft.com/en-us/library/office/aa580234(v=exchg.150).aspx
    ELEMENT_NAME = 'ItemId'

    ID_ATTR = 'Id'
    CHANGEKEY_ATTR = 'ChangeKey'

    __slots__ = ('id', 'changekey')

    def __init__(self, id, changekey):
        self.id = id
        self.changekey = changekey
        self.clean()

    def clean(self):
        if not isinstance(self.id, string_types) or not self.id:
            raise ValueError("id '%s' must be a non-empty string" % id)
        if not isinstance(self.changekey, string_types) or not self.changekey:
            raise ValueError("changekey '%s' must be a non-empty string" % self.changekey)

    def to_xml(self, version):
        self.clean()
        elem = create_element(self.request_tag())
        # Use .set() to not fill up the create_element() cache with unique values
        elem.set(self.ID_ATTR, self.id)
        elem.set(self.CHANGEKEY_ATTR, self.changekey)
        return elem

    @classmethod
    def from_xml(cls, elem):
        if elem is None:
            return None
        assert elem.tag == cls.response_tag(), (cls, elem.tag, cls.response_tag())
        res = cls(id=elem.get(cls.ID_ATTR), changekey=elem.get(cls.CHANGEKEY_ATTR))
        elem.clear()
        return res

    def __eq__(self, other):
        # A more efficient version of super().__eq__
        if other is None:
            return False
        return self.id == other.id and self.changekey == other.changekey


class ParentItemId(ItemId):
    # MSDN: https://msdn.microsoft.com/en-us/library/office/aa563720(v=exchg.150).aspx
    ELEMENT_NAME = 'ParentItemId'
    NAMESPACE = MNS

    __slots__ = ItemId.__slots__


class RootItemId(ItemId):
    # MSDN: https://msdn.microsoft.com/en-us/library/office/bb204277(v=exchg.150).aspx
    ELEMENT_NAME = 'RootItemId'
    NAMESPACE = MNS

    ID_ATTR = 'RootItemId'
    CHANGEKEY_ATTR = 'RootItemChangeKey'

    __slots__ = ItemId.__slots__


class Mailbox(EWSElement):
    # MSDN: https://msdn.microsoft.com/en-us/library/office/aa565036(v=exchg.150).aspx
    ELEMENT_NAME = 'Mailbox'
    MAILBOX_TYPES = {'Mailbox', 'PublicDL', 'PrivateDL', 'Contact', 'PublicFolder', 'Unknown', 'OneOff'}

    __slots__ = ('name', 'email_address', 'mailbox_type', 'item_id')

    def __init__(self, name=None, email_address=None, mailbox_type=None, item_id=None):
        # There's also the 'RoutingType' element, but it's optional and must have value "SMTP"
        self.name = name
        self.email_address = email_address
        self.mailbox_type = mailbox_type
        self.item_id = item_id
        self.clean()

    def clean(self):
        if self.name is not None:
            assert isinstance(self.name, string_types)
        if self.email_address is not None:
            assert isinstance(self.email_address, string_types)
        if self.mailbox_type is not None:
            assert self.mailbox_type in self.MAILBOX_TYPES
        if self.item_id is not None:
            assert isinstance(self.item_id, ItemId)
        if not self.email_address and not self.item_id:
            # See "Remarks" section of https://msdn.microsoft.com/en-us/library/office/aa565036(v=exchg.150).aspx
            raise AttributeError('Mailbox must have either email_address or item_id')

    def to_xml(self, version):
        self.clean()
        mailbox = create_element(self.request_tag())
        if self.name:
            add_xml_child(mailbox, 't:Name', self.name)
        if self.email_address:
            add_xml_child(mailbox, 't:EmailAddress', self.email_address)
        if self.mailbox_type:
            add_xml_child(mailbox, 't:MailboxType', self.mailbox_type)
        if self.item_id:
            set_xml_value(mailbox, self.item_id, version)
        return mailbox

    @classmethod
    def from_xml(cls, elem):
        if elem is None:
            return None
        assert elem.tag == cls.response_tag(), (elem.tag, cls.response_tag())
        res = cls(
            name=get_xml_attr(elem, '{%s}Name' % TNS),
            email_address=get_xml_attr(elem, '{%s}EmailAddress' % TNS),
            mailbox_type=get_xml_attr(elem, '{%s}MailboxType' % TNS),
            item_id=ItemId.from_xml(elem=elem.find(ItemId.response_tag())),
        )
        elem.clear()
        return res

    def __hash__(self):
        # Exchange may add 'mailbox_type' and 'name' on insert. We're satisfied if the item_id or email address matches.
        if self.item_id:
            return hash(self.item_id)
        return hash(self.email_address.lower())


class Attendee(EWSElement):
    # MSDN: https://msdn.microsoft.com/en-us/library/office/aa580339(v=exchg.150).aspx
    ELEMENT_NAME = 'Attendee'
    RESPONSE_TYPES = {'Unknown', 'Organizer', 'Tentative', 'Accept', 'Decline', 'NoResponseReceived'}

    __slots__ = ('mailbox', 'response_type', 'last_response_time')

    def __init__(self, mailbox, response_type, last_response_time=None):
        self.mailbox = mailbox
        self.response_type = response_type
        self.last_response_time = last_response_time
        self.clean()

    def clean(self):
        if isinstance(self.mailbox, string_types):
            self.mailbox = Mailbox(email_address=self.mailbox)
        assert isinstance(self.mailbox, Mailbox)
        assert self.response_type in self.RESPONSE_TYPES
        if self.last_response_time is not None:
            assert isinstance(self.last_response_time, EWSDateTime)

    def to_xml(self, version):
        self.clean()
        attendee = create_element(self.request_tag())
        set_xml_value(attendee, self.mailbox, version)
        add_xml_child(attendee, 't:ResponseType', self.response_type)
        if self.last_response_time:
            add_xml_child(attendee, 't:LastResponseTime', self.last_response_time)
        return attendee

    @classmethod
    def from_xml(cls, elem):
        if elem is None:
            return None
        assert elem.tag == cls.response_tag(), (cls, elem.tag, cls.response_tag())
        last_response_time = get_xml_attr(elem, '{%s}LastResponseTime' % TNS)
        res = cls(
            mailbox=Mailbox.from_xml(elem=elem.find(Mailbox.response_tag())),
            response_type=get_xml_attr(elem, '{%s}ResponseType' % TNS) or 'Unknown',
            last_response_time=EWSDateTime.from_string(last_response_time) if last_response_time else None,
        )
        elem.clear()
        return res

    def __hash__(self):
        # TODO: maybe take 'response_type' and 'last_response_time' into account?
        return hash(self.mailbox)


class RoomList(Mailbox):
    # MSDN: https://msdn.microsoft.com/en-us/library/office/dd899514(v=exchg.150).aspx
    ELEMENT_NAME = 'RoomList'
    NAMESPACE = MNS

    @classmethod
    def response_tag(cls):
        # In a GetRoomLists response, room lists are delivered as Address elements
        # MSDN: https://msdn.microsoft.com/en-us/library/office/dd899404(v=exchg.150).aspx
        return '{%s}Address' % TNS


class Room(Mailbox):
    # MSDN: https://msdn.microsoft.com/en-us/library/office/dd899479(v=exchg.150).aspx
    ELEMENT_NAME = 'Room'

    @classmethod
    def from_xml(cls, elem):
        if elem is None:
            return None
        assert elem.tag == cls.response_tag(), (elem.tag, cls.response_tag())
        id_elem = elem.find('{%s}Id' % TNS)
        res = cls(
            name=get_xml_attr(id_elem, '{%s}Name' % TNS),
            email_address=get_xml_attr(id_elem, '{%s}EmailAddress' % TNS),
            mailbox_type=get_xml_attr(id_elem, '{%s}MailboxType' % TNS),
            item_id=ItemId.from_xml(elem=id_elem.find(ItemId.response_tag())),
        )
        elem.clear()
        return res