"""SDMX Information Model (SDMX-IM)

This module implements many of the classes described in the SDMX-IM
specification ('spec'), which is available from:

- https://sdmx.org/?page_id=5008
- https://sdmx.org/wp-content/uploads/
    SDMX_2-1-1_SECTION_2_InformationModel_201108.pdf

Details of the implementation:
- the IPython traitlets package is used to enforce the types of attributes
  that reference instances of other classes. Two custom trait types are used:
  - DictLikeTrait: a dict-like object with attribute and integer index access.
    See pandasdmx.util.
  - InternationalStringTrait.
- class definitions are grouped by section of the spec, but these section
  appear out of order so that dependent classes are defined first.

The module also implements extra classes that are NOT described in the spec,
but are used in XML and JSON messages: Message, StructureMessage, DataMessage,
Header, and Footer. These appear last.

"""
from copy import copy
from datetime import date, datetime, timedelta
from enum import Enum
from operator import attrgetter

from traitlets import (
    Any,
    Bool,
    CInt,
    Dict,
    Float,
    HasTraits,
    Instance,
    Int,
    List,
    Set,
    This,
    TraitType,
    Unicode,
    Union,
    UseEnum,
    )

from pandasdmx.util import DictLikeTrait


# TODO read this from the environment
DEFAULT_LOCALE = 'EN_ca'


# 3.2: Base structures

class InternationalString(HasTraits):
    """SDMX-IM InternationalString.

    SDMX-IM LocalisedString is not implemented. Instead, the 'localizations' is
    a mapping where:
     - keys correspond to the 'locale' property of LocalisedString.
     - values correspond to the 'label' property of LocalisedString.
    """
    localizations = Dict(Instance(Unicode))

    def __init__(self, value=None, **kwargs):
        if isinstance(value, str):
            self.localizations[DEFAULT_LOCALE] = value
        elif isinstance(value, tuple) and len(value) == 2:
            self.localizations[value[0]] = value[1]
        elif value is None:
            self.localizations.update(kwargs)
        else:
            raise ValueError

    def set_label(self, value):
        self.localizations[DEFAULT_LOCALE] = value

    # Convenience access
    def __getitem__(self, locale):
        return self.localizations[locale]

    def __setitem__(self, locale, label):
        self.localizations[locale] = label

    def __add__(self, other):
        result = copy(self)
        result.localizations.update(other.localizations)
        return result

    def __str__(self):
        try:
            return self.localizations[DEFAULT_LOCALE]
        except KeyError:
            # No label in the default locale; use the first stored value
            return next(iter(self.localizations.values()))

    def __repr__(self):
        return '\n'.join(['{}: {}'.format(*kv) for kv in
                          sorted(self.localizations.items())])


class InternationalStringTrait(TraitType):
    """Trait type for InternationalString.

    With trailets.Instance, a locale must be provided for every label:

    >>> class Foo(HasTraits):
    >>>     name = Instance(InternationalString)
    >>>
    >>> f = Foo()
    >>> f.name['en'] = "Foo's name in English"

    With InternationalStringTrait, the DEFAULT_LOCALE is automatically selected
    when setting with a string:

    >>> class Bar(HasTraits):
    >>>     name = InternationalStringTrait
    >>>
    >>> b = Bar()
    >>> b.name = "Bar's name in English"

    """
    default_value = InternationalString()

    def validate(self, obj, value):
        if isinstance(value, InternationalString):
            return value
        try:
            return obj._trait_values[self.name] + InternationalString(value)
        except ValueError:
            self.error(obj, value)


class Annotation(HasTraits):
    id = Unicode()
    title = Unicode()
    type = Unicode()
    url = Unicode()

    text = InternationalStringTrait()


class AnnotableArtefact(HasTraits):
    annotations = List(Instance(Annotation))


class IdentifiableArtefact(AnnotableArtefact):
    id = Unicode()
    uri = Unicode()
    urn = Unicode()

    def __str__(self):
        return self.id

    def __repr__(self):
        return '<{}: {}>'.format(self.__class__.__name__, self.id)


class NameableArtefact(IdentifiableArtefact):
    name = InternationalStringTrait()
    description = InternationalStringTrait(allow_none=True)

    def __repr__(self):
        return "<{}: '{}'='{}'>".format(
            self.__class__.__name__,
            self.id,
            str(self.name))


class VersionableArtefact(NameableArtefact):
    version = Unicode()
    valid_from = Unicode(allow_none=True)
    valid_to = Unicode(allow_none=True)


class MaintainableArtefact(VersionableArtefact):
    final = Bool()
    is_external_reference = Bool()
    service_url = Unicode()
    structure_url = Unicode()
    maintainer = Instance('pandasdmx.model.Agency')


# 3.4: Data Types

ActionType = Enum('ActionType', 'delete replace append information')

UsageStatus = Enum('UsageStatus', 'mandatory conditional')

FacetValueType = Enum(
    'FacetValueType',
    'string bigInteger integer long short decimal float double boolean uri'
    'count inclusiveValueRange alpha alphaNumeric numeric exclusiveValueRange'
    'incremental observationalTimePeriod standardTimePeriod basicTimePeriod'
    'gregorianTimePeriod gregorianYearMonth gregorianDay reportingTimePeriod'
    'reportingYear reportingSemester reportingTrimester reportingQuarter'
    'reportingMonth reportingWeek reportingDay dateTime timesRange month'
    'monthDay day time duration keyValues identifiableReference'
    'dataSetReference')


# 3.5: Item Scheme

class Item(NameableArtefact):
    parent = Instance(This, allow_none=True)
    child = List(Instance(This))


class ItemScheme(MaintainableArtefact):
    is_partial = Bool()
    items = List(Instance(Item))

    def __repr__(self):
        return "<{}: '{}', {} items>".format(
            self.__class__.__name__,
            self.id,
            len(self.items))


# 3.6: Structure

class FacetType(HasTraits):
    isSequence = Bool()
    min_length = Int()
    max_length = Int()
    min_value = Float()
    max_value = Float()
    start_value = Float()
    end_value = Unicode()
    interval = Float()
    time_interval = Instance(timedelta)
    decimals = Int()
    pattern = Unicode()
    start_time = Instance(datetime)
    end_time = Instance(datetime)


class Facet(HasTraits):
    type = Instance(FacetType)
    value = Unicode()
    value_type = UseEnum(FacetValueType)


class Representation:
    enumerated = List(Instance(ItemScheme))
    non_enumerated = Set(Instance(Facet))


# 4.4: Concept Scheme

class ISOConceptReference(HasTraits):
    agency = Unicode()
    id = Unicode()
    scheme_id = Unicode()


class Concept(Item):
    core_representation = Instance(Representation, allow_none=True)
    iso_concept = Instance(ISOConceptReference)


class ConceptScheme(ItemScheme):
    items = List(Instance(Concept))


# 3.3: Basic Inheritance

class Component(IdentifiableArtefact):
    concept_identity = Instance(Concept)
    local_representation = Instance(Representation)


class ComponentList(IdentifiableArtefact):
    components = List(Instance(Component))

    # Convenience access to the components
    def append(self, value):
        self.components.append(value)

    def __iter__(self):
        return iter(self.components)

    def __repr__(self):
        return '<{}: {}>'.format(self.__class__.__name__,
                                 '; '.join(map(str, self.components)))


# 4.3: Codelist

class Code(Item):
    pass


class Codelist(ItemScheme):
    items = List(Instance(Code))


# 4.5: Category Scheme

class Category(Item):
    pass


class CategoryScheme(ItemScheme):
    items = List(Instance(Category))


class Categorisation(MaintainableArtefact):
    category = Instance(Category)
    artefact = Instance(IdentifiableArtefact)


# 4.6: Organisations

class Organisation(Item):
    pass


class Agency(Organisation):
    pass


# 10.2: Constraint inheritance

class ConstrainableArtefact:
    pass


# 10.3: Constraints

ConstraintRoleType = Enum('ConstraintRoleType', 'allowable actual')


class ConstraintRole(HasTraits):
    role = UseEnum(ConstraintRoleType)


class KeyValidatorMixin(object):
    '''
    Mix-in class with methods for key validation. Relies on properties computing
    code sets, constrained codes etc. Subclasses are DataMessage and
    CodelistHandler which is, in turn, inherited by StructureMessage.
    '''

    def _in_codes(self, key, raise_error=True):
        '''
        key: a prepared key, i.e. multiple values within a dimension
        must be represented as list of strings.

        This method is called by self._in_constraints. Thus it does not
        be called from application code.

args:
    key(dict): normalized key, i.e. values must be lists of str
    raises_error(bool): if True (default),
        ValueError is raised if at least one value within key
        is not in the (unconstrained) codes. Otherwise, False is returned.
        If all values from key are in the respective code list,
        True is returned

        '''
        # First, check keys against dim IDs
        invalid = [k for k in key if k not in self._dim_ids]
        if invalid:
            raise ValueError(
                'Invalid dimension ID(s) {0}, allowed are: {1}'.format(invalid, self._dim_ids))
        # Raise error if some value is not of type list
        if [k for k in key.values() if not isinstance(k, list)]:
            raise TypeError(
                'All values of the key-dict must be of type ``list``.')
        # Check values against codelists
        invalid = defaultdict(list)
        for k, values in key.items():
            for v in values:
                if v not in self._dim_codes[k]:
                    invalid[k].append(v)
        if invalid:
            if raise_error:
                raise ValueError(
                    'Value(s) not in codelists.', invalid)
            else:
                return False
        return True

    def _in_constraints(self, key, raise_error=True):
        '''
        check key against all constraints, i.e. the constrained
        code lists.

        args:
    key(dict): normalized key, i.e. values must be lists of str
    raises_error(bool): if True (default),
        ValueError is raised if at least one value within key
        is not in the (unconstrained) codes. Otherwise, False is returned.
        If all values from key are in the respective code list,
        True is returned

        return True if key satisfies all constraints. Otherwise, return False or
        raise ValueError, depending on the value of ``raise_error``
        '''
        # validate key against unconstrained codelists
        self._in_codes(key, raise_error)
        # Validate key against constraints if any
        invalid = defaultdict(list)
        for k, values in key.items():
            for v in values:
                if v not in self._constrained_codes[k]:
                    invalid[k].append(v)
        if invalid:
            if raise_error:
                raise ValueError(
                    'Value(s) not in constrained codelists.', invalid)
            else:
                return False
        return True


class CodelistHandler(KeyValidatorMixin):
    '''
    High-level API implementing the
    application of content constraints to codelists. It is primarily
    used as a mixin to StructureMessage instances containing codelists,
    a DSD, Dataflow and related constraints. However, it
    may also be used stand-online. It computes
    the constrained codelists in collaboration with
    Constrainable, ContentConstraint and Cube Region classes.
    '''

    def __init__(self, *args, **kwargs):
        '''
        Prepare computation of constrained codelists using the
        cascading mechanism described in Chap. 8 of the Technical Guideline (Part 6 of the SDMX 2.1 standard)

        args:

            constrainables(list of model.Constrainable instances):
                Constrainable artefacts in descending order sorted by
                cascading level (e.g., `[DSD, Dataflow]`). At position 0
                there must be the DSD. Defaults to [].
                If not given, try to
                collect the constrainables from the StructureMessage.
                this will be the most common use case.
        '''
        super(CodelistHandler, self).__init__(*args, **kwargs)
        constrainables = kwargs.get('constrainables', [])
        if constrainables:
            self.__constrainables = constrainables
        elif (hasattr(self, 'datastructure')
              and hasattr(self, 'codelist')):
            self.in_codes = self._in_codes
            if hasattr(self, 'constraint'):
                self.in_constraints = self._in_constraints
            else:
                self.in_constraints = self.in_codes

    @property
    def _constrainables(self):
        if not hasattr(self, '__constrainables'):
            self.__constrainables = []
            # Collecting any constrainables from the StructureMessage
            # is only meaningful if the Message contains but one DataFlow and
            # DSD.
            if (hasattr(self, 'datastructure') and len(self.datastructure) == 1):
                dsd = self.datastructure.aslist()[0]
                self.__constrainables.append(dsd)
                if hasattr(self, 'dataflow'):
                    flow = self.dataflow.aslist()[0]
                    self.__constrainables.append(flow)
                if hasattr(self, 'provisionagreement'):
                    for p in self.provisionagreement.values():
                        if flow in p.constrained_by:
                            self.__constrainables.append(p)
                            break
        return self.__constrainables

    @property
    def _dim_ids(self):
        '''
        Collect the IDs of dimensions which are
        represented by codelists (this excludes TIME_PERIOD etc.)
        '''
        if not hasattr(self, '__dim_ids'):
            self.__dim_ids = tuple(d.id for d in self._constrainables[0].dimensions.aslist()
                                   if d.local_repr.enum)
        return self.__dim_ids

    @property
    def _attr_ids(self):
        '''
        Collect the IDs of attributes which are
        represented by codelists
        '''
        if not hasattr(self, '__attr_ids'):
            self.__attr_ids = tuple(d.id for d in self._constrainables[0].attributes.aslist()
                                    if d.local_repr.enum)
        return self.__attr_ids

    @property
    def _dim_codes(self):
        '''
        Cached property returning a DictLike mapping dim ID's from the DSD to
        frozensets containing all code IDs from the codelist
        referenced by the Concept describing the respective dimensions.
        '''
        if not hasattr(self, '__dim_codes'):
            if self._constrainables:
                enum_components = [d for d in self._constrainables[0].dimensions.aslist()
                                   if d.local_repr.enum]
                self.__dim_codes = DictLike({d.id: frozenset(d.local_repr.enum())
                                             for d in enum_components})
            else:
                self.__dim_codes = {}
        return self.__dim_codes

    @property
    def _attr_codes(self):
        '''
        Cached property returning a DictLike mapping attribute ID's from the DSD to
        frozensets containing all code IDs from the codelist
        referenced by the Concept describing the respective attributes.
        '''
        if not hasattr(self, '__attr_codes'):
            if self._constrainables:
                enum_components = [d for d in self._constrainables[0].attributes.aslist()
                                   if d.local_repr.enum]
                self.__attr_codes = DictLike({d.id: frozenset(d.local_repr.enum())
                                              for d in enum_components})
            else:
                self.__attr_codes = {}
        return self.__attr_codes

    @property
    def _constrained_codes(self):
        '''
        Cached property returning a DictLike mapping dim ID's from the DSD to
        frozensets containing the code IDs from the codelist
        referenced by the Concept for the dimension after applying
        all content constraints to the codelists. Those contenten constraints are
        retrieved pursuant to an implementation of the algorithm described in the
        SDMX 2.1 Technical Guidelines (Part 6) Chap. 9. Hence, constraints
        may constrain the DSD, dataflow definition or provision-agreement.
        '''
        if not hasattr(self, '__constrained_codes'):
            # Run the cascadation mechanism from Chap. 8 of the SDMX 2.1
            # Technical Guidelines.
            cur_dim_codes, cur_attr_codes = self._dim_codes, self._attr_codes
            for c in self._constrainables:
                cur_dim_codes, cur_attr_codes = c.apply(
                    cur_dim_codes, cur_attr_codes)
            self.__constrained_codes = DictLike(cur_dim_codes)
            self.__constrained_codes.update(cur_attr_codes)
        return self.__constrained_codes


class Constraint(MaintainableArtefact):
    # data_content_keys = Instance(DataKeySet, allow_none=True)
    # metadata_content_keys = Instance(MetadataKeySet, allow_none=True)
    role = Set(Instance(ConstraintRole))


class SelectionValue:
    pass


class MemberSelection(HasTraits):
    included = Bool()
    values_for = Instance(Component)
    values = Set(Instance(SelectionValue))


class CubeRegion(HasTraits):
    included = Bool()
    member = Set(Instance(MemberSelection))

    def __contains__(self, v):
        key, value = v
        kv = self.key_values
        if key not in kv.keys():
            raise KeyError(
                'Unknown key: {0}. Allowed keys are: {1}'.format(
                    key, list(kv.keys())))
        return (value in kv[key]) == self.include


class ContentConstraint(Constraint):
    data_content_region = Instance(CubeRegion, allow_none=True)
    # metadata_content_region = Instance(MetadataTargetRegion, allow_none=True)

    def apply(self, dim_codes=None, attr_codes=None):
        '''
        Compute the constrained code lists as frozensets by
        merging the constraints resulting from all cube regions into a dict of sets of valid codes
        for dimensions and attributes respectively.
        We assume that each codelist is constrained by at most one cube
        region so that no set operations are required.

        Return tuple of constrained_dimension_codes(dict), constrained_attribute_codes(dict)
        '''
        dimension, attribute = {}, {}
        for c in self.cube_region:
            d, a = c.apply(dim_codes, attr_codes)
            if d:
                dimension.update(d)
            if a:
                attribute.update(a)
        return dimension, attribute


# 5.2: Data Structure Defintion

class DimensionComponent(Component):
    order = Int()


class Dimension(DimensionComponent):
    pass


class TimeDimension(DimensionComponent):
    pass


class MeasureDimension(DimensionComponent):
    pass


class PrimaryMeasure(Component):
    pass


class MeasureDescriptor(ComponentList):
    components = List(Instance(PrimaryMeasure))


class DataAttribute(Component):
    usage_status = Instance(UsageStatus)


class ReportingYearStartDay(DataAttribute):
    pass


class AttributeDescriptor(ComponentList):
    components = List(Instance(DataAttribute))


class Structure(MaintainableArtefact):
    grouping = Instance(ComponentList)


class StructureUsage(MaintainableArtefact):
    structure = Instance(Structure)


class DimensionDescriptor(ComponentList):
    components = List(Union([
        Instance(Dimension),
        Instance(MeasureDimension),
        Instance(TimeDimension),
        ]))

    def order_key(self, key):
        """Return a key ordered according to the DSD."""
        result = Key()
        for dim in sorted(self.components, key=attrgetter('order')):
            try:
                result[dim.id] = key[dim.id]
            except KeyError:
                continue
        return result


class GroupDimensionDescriptor(DimensionDescriptor):
    attachment_constraint = Bool()
    # constraint = Instance(AttachmentConstraint, allow_none=True)


class DataStructureDefinition(Structure, ConstrainableArtefact):
    attributes = Instance(AttributeDescriptor, args=())
    dimensions = Instance(DimensionDescriptor)
    measures = Instance(MeasureDescriptor)
    group_dimensions = Instance(GroupDimensionDescriptor)

    @property
    def grouping(self):
        return


class DataflowDefinition(StructureUsage, ConstrainableArtefact):
    pass


# 5.4: Data Set

class KeyValue(HasTraits):
    id = Unicode()
    value = Any()

    def __eq__(self, other):
        """Compare the value to a Python built-in type, e.g. str."""
        return self.value == other

    def __str__(self):
        return '{0.id}: {0.value}'.format(self)


TimeKeyValue = KeyValue


class Key(HasTraits):
    """SDMX Key class.

    The constructor takes an optional list of keyword arguments; the keywords
    are used as Dimension IDs, and the values as KeyValues.

    For convience, the values of the key may be accessed directly:

    >>> k = Key(foo=1, bar=2)
    >>> k.values['foo']
    1
    >>> k['foo']
    1

    """
    values = DictLikeTrait(Instance(KeyValue))
    described_by = Instance(DimensionDescriptor, allow_none=True)

    def __init__(self, arg=None, **kwargs):
        if arg:
            if len(kwargs):
                raise ValueError("Key() accepts either a single argument, or "
                                 "keyword arguments; not both.")
            kwargs.update(arg)
        self.described_by = kwargs.pop('described_by', None)
        for id, value in kwargs.items():
            self.values[id] = KeyValue(id=id, value=value)

    def __len__(self):
        """The length of the key is the number of KeyValues it contains."""
        return len(self.values)

    def __contains__(self, other):
        try:
            return all([self.values[k] == v for k, v in other.values.items()])
        except KeyError:
            # 'k' in other does not appear in this Key()
            return False

    # Convenience access to values by name
    def __getitem__(self, name):
        return self.values[name]

    def __setitem__(self, name, value):
        # Convert a bare string or other Python object to a KeyValue instance
        if not isinstance(value, KeyValue):
            value = KeyValue(id=name, value=value)
        self.values[name] = value

    # Convenience access to values by attribute
    def __getattr__(self, name):
        try:
            # To avoid recursion, use the underlying traitlets private member
            return self._trait_values['values'][name]
        except KeyError:
            raise AttributeError

    def __str__(self):
        return '({})'.format(', '.join(map(str, self.values.values())))

    # Copying
    def __copy__(self):
        result = Key()
        if self.described_by:
            result.described_by = self.described_by
        for kv in self.values.values():
            result[kv.id] = kv
        return result

    def copy(self, arg=None, **kwargs):
        result = copy(self)
        for id, value in kwargs.items():
            result[id] = value
        return result

    def __add__(self, other):
        if not isinstance(other, Key):
            raise NotImplementedError
        result = copy(self)
        for id, value in other.values.items():
            result[id] = value
        return result

    def __radd__(self, other):
        if other is None:
            return copy(self)
        else:
            raise NotImplementedError

    def __eq__(self, other):
        return all([a == b for a, b in zip(self.values, other.values)])

    def order(self, value=None):
        if value is None:
            value = self
        try:
            return self.described_by.order_key(value)
        except AttributeError:
            return value

    def get_values(self):
        return tuple([kv.value for kv in self.values.values()])


SeriesKey = Key


class GroupKey(Key):
    id = Unicode()
    described_by = Instance(GroupDimensionDescriptor, allow_none=True)


class AttributeValue(HasTraits):
    """SDMX-IM AttributeValue.

    In the spec, AttributeValue is an abstract class. Here, it serves as both
    the concrete subclasses CodedAttributeValue and UncodedAttributeValue.
    """
    value = Union([Unicode(), Instance(Code)])
    value_for = Instance(DataAttribute, allow_none=True)
    start_date = Instance(date)

    def __eq__(self, other):
        return self.value == other

    def __str__(self):
        return self.value

    def __repr__(self):
        return '<{}: {} for {}>'.format(self.__class__.__name__, self.value,
                                        self.value_for)


class Observation(HasTraits):
    """SDMX-IM Observation.

    This class also implements the spec classes ObservationValue,
    UncodedObservationValue, and CodedObservation.
    """
    attrib = DictLikeTrait(Instance(AttributeValue))
    series_key = Instance(SeriesKey, allow_none=True)
    dimension = Instance(Key, allow_none=True)
    value = Union([Any(), Instance(Code)])
    value_for = Instance(PrimaryMeasure, allow_none=True)

    @property
    def dim(self):
        if len(self.key) == 1:
            return self.key.values[0]
        else:
            raise ValueError("Observations with keys of length > 1 have no "
                             "dimension.")

    @property
    def key(self):
        return self.series_key + self.dimension

    def __len__(self):
        return len(self.key)

    def __str__(self):
        return '{0.key}: {0.value}'.format(self)

    def add_attributes(self, keys, values):
        for k, v in zip(keys, values):
            self.attrib[k] = AttributeValue(value=v)


class DataSet(AnnotableArtefact):
    action = UseEnum(ActionType)
    attrib = DictLikeTrait(Instance(AttributeValue))
    valid_from = Unicode(allow_none=True)
    structured_by = Instance(DataStructureDefinition)
    obs = List(Instance(Observation))

    def add_attributes(self, keys, values):
        for k, v in zip(keys, values):
            self.attrib[k] = AttributeValue(value=v)


# Message-related classes (not part of the SDMX-IM)

class Header(HasTraits):
    error = Unicode()
    id = Unicode()
    prepared = Unicode()
    receiver = Unicode()
    sender = Union([Instance(Item), Unicode()])


class Footer(HasTraits):
    severity = Unicode()
    text = List(Instance(InternationalString))
    code = CInt()


class Message(HasTraits):
    """Message."""
    header = Instance(Header)
    footer = Instance(Footer, allow_none=True)


class StructureMessage(Message):
    codelist = Instance(Codelist)
    concept_scheme = Instance(ConceptScheme)
    dataflow = Instance(DataflowDefinition)
    structure = Instance(DataStructureDefinition)
    constraint = Instance(ContentConstraint)
    category_scheme = Instance(CategoryScheme)


class _AllDimensions:
    pass


AllDimensions = _AllDimensions()


class DataMessage(Message):
    data = List(Instance(DataSet))
    structure = Instance(DataStructureDefinition)
    observation_dimension = Union([Instance(_AllDimensions),
                                   List(Instance(Dimension))], allow_none=True)
