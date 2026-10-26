---
title: Parameters
head:
  - tag: style
    content: ':root { --sl-content-width: 70rem; }'
---

This reference maps Earthdata MCP tool parameters to the upstream API arguments and schema fields behind them. It provides consumers with a clear picture of current API integration depth and search capabilities. Each tool's section names the endpoint and schema it is built on.

<terra-alert open variant="information" appearance="subtle">
	<terra-icon slot="icon" name="solid-information-circle" library="heroicons"></terra-icon>
	All search tools globally support the <strong>limit</strong>, <strong>cursor</strong>, and <strong>fields</strong> parameters for pagination and response filtering. These are omitted from the tables below for brevity.
</terra-alert>

> **Note on Harmony tools:** Unlike the CMR-backed tools above, the four Harmony transformation tools below do not query CMR's `/search` endpoints or use UMM schemas. They call the [Harmony](https://harmony.earthdata.nasa.gov/) API directly via the official [harmony-py](https://github.com/nasa/harmony-py) client library. Parameter/field tables for these tools reference harmony-py and the Harmony API's own JSON response shapes instead of CMR API parameters and UMM JSON paths.
>
> **Authentication required:** Unlike the CMR-backed discovery tools, all four Harmony tools require an authenticated Earthdata Login access token (retrieved via `get_access_token()`) to call Harmony's API on the user's behalf.

---

## `get_collections`
Searches for datasets (collections) using scientific keywords, instruments, platforms, or spatial/temporal constraints.
- **CMR Endpoint:** [`/search/collections`](https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html#collection-search)
- **Schema:** [UMM-C (v1.18.3)](https://cdn.earthdata.nasa.gov/umm/collection/v1.18.3)

### Input Parameters
| Status | MCP Argument | CMR API Parameter | Description |
|---|---|---|---|
| ✅ | `keyword` | `keyword` | Free-text search across a collection's indexed metadata, case insensitive. All words must match, so extra terms narrow the search rather than widen it. |
| ✅ | `concept_id` | `concept_id` | Exact CMR concept ID, e.g. `C2036882064-POCLOUD`. Direct lookup of a known collection. |
| ✅ | `short_name` | `short_name` | Collection short name, e.g. `MOD11A1`. Exact match unless the `*` or `?` wildcards are used. |
| ✅ | `provider` | `provider` | Archive center that published the collection, e.g. `PODAAC`, `GES_DISC`. Cloud migration has renamed some providers, and a stale ID returns no results rather than an error. |
| ✅ | `temporal_start_date` | `temporal` | Start of the temporal window, ISO 8601. Matches collections whose declared range overlaps it. |
| ✅ | `temporal_end_date` | `temporal` | End of the temporal window, ISO 8601. Matches collections whose declared range overlaps it. |
| ✅ | `spatial_wkt_geometry` | `polygon, point, bounding_box` | Area of interest as a WKT `POLYGON`, `POINT`, or `LINESTRING`. Matches collections whose declared extent intersects it, so a precise shape avoids false positives. |
| ✅ | `platform` | `platform` | Platform short names to filter by, e.g. `Terra`, `Aqua`. Narrows a search to one mission's instruments. |
| ✅ | `instrument` | `instrument` | Instrument short names to filter by, e.g. `MODIS`, `VIIRS`. Matches the instrument field rather than the whole record, so it is tighter than the same name as a keyword. |
| ✅ | `processing_level_id` | `processing_level_id` | Processing levels to filter by, e.g. `3`, `3A`. Distinguishes L2 swath from L3 gridded products. |
| ✅ | `has_granules` | `has_granules` | When true, limits results to collections that hold granules. CMR also carries metadata-only records for planned missions and datasets archived elsewhere. |
| ❌ | N/A | `doi` | Search by digital object identifier |
| ❌ | N/A | `project` | Search by project/campaign name |
| ❌ | N/A | `data_center` | Search by data center/archive center |
| ❌ | N/A | `science_keywords` | Search by GCMD science keywords hierarchy |
| ❌ | N/A | `updated_since` | Filter by recently updated collections |

### Output Fields
| Status | MCP Response Field | UMM JSON Path | Transformed | Description |
|---|---|---|---|---|
| ✅ | `abstract` | `Abstract` | | Collection summary or abstract |
| ✅ | `archive_and_distribution_information` | `ArchiveAndDistributionInformation` | ✅ | File formats and media types (e.g., [{format, media_type}]) |
| ✅ | `bounding_box` | `SpatialExtent.HorizontalSpatialDomain.Geometry.BoundingRectangles` | ✅ | [West, South, East, North] Minimum Bounding Rectangle |
| ✅ | `collection_data_type` | `CollectionDataType` | | e.g., SCIENCE_QUALITY, NEAR_REAL_TIME |
| ✅ | `collection_progress` | `CollectionProgress` | | ACTIVE, COMPLETE, DEPRECATED, or PLANNED |
| ✅ | `concept_id` | `meta.concept-id` | | CMR collection concept ID |
| ✅ | `data_centers` | `DataCenters` | ✅ | Archiving DAACs — array of {role, short_name} |
| ✅ | `doi` | `DOI` | | Digital Object Identifier |
| ✅ | `entry_title` | `EntryTitle` | | Collection title |
| ✅ | `instruments` | `Platforms.Instruments.ShortName` | ✅ | Instrument short names |
| ✅ | `is_ongoing` | `IsOngoing` | ✅ | Whether the collection is ongoing |
| ✅ | `native_id` | `meta.native-id` | | The native ID of the collection record |
| ✅ | `platforms` | `Platforms.ShortName` | ✅ | Platform short names |
| ✅ | `processing_level_id` | `ProcessingLevel.Id` | | Processing level (e.g., L3, L4) |
| ✅ | `provider_id` | `meta.provider-id` | | The provider ID of the collection |
| ✅ | `related_urls` | `RelatedUrls` | ✅ | List of related URLs (e.g., documentation, guides) |
| ✅ | `revision_id` | `meta.revision-id` | | The revision ID of the collection metadata |
| ✅ | `science_keywords` | `ScienceKeywords` | | GCMD science keyword hierarchy (Category/Topic/Term/VariableLevel) |
| ✅ | `short_name` | `ShortName` | | Collection short name |
| ✅ | `spatial_resolution` | `SpatialExtent.HorizontalSpatialDomain.ResolutionAndCoordinateSystem` | ✅ | Human-readable spatial resolution |
| ✅ | `temporal_resolution` | `TemporalExtents.TemporalResolution` | ✅ | Human-readable temporal resolution |
| ✅ | `time_end` | `TemporalExtents.RangeDateTimes.EndingDateTime` | ✅ | End of temporal coverage |
| ✅ | `time_start` | `TemporalExtents.RangeDateTimes.BeginningDateTime` | ✅ | Start of temporal coverage |
| ✅ | `version` | `Version` | | Collection version |
| ❌ | N/A | `AccessConstraints` | | Access constraints and authorization requirements |
| ❌ | N/A | `AdditionalAttributes` | | Provider-specific additional attributes |
| ❌ | N/A | `ContactGroups/ContactPersons` | | Point of contact information |
| ❌ | N/A | `Projects` | | Projects or campaigns associated with the collection |
| ❌ | N/A | `SpatialKeywords` | | Geographic location keywords |

---

## `get_granules`
Searches for specific data files (granules) within a collection to verify actual data availability for a given time and location.
- **CMR Endpoint:** [`/search/granules`](https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html#granule-search)
- **Schema:** [UMM-G (v1.6.5)](https://cdn.earthdata.nasa.gov/umm/granule/v1.6.5)

### Input Parameters
| Status | MCP Argument | CMR API Parameter | Description |
|---|---|---|---|
| ✅ | `collection_concept_id` | `collection_concept_id` | Parent collection to search within, e.g. `C2723758340-GES_DISC`. Required. |
| ✅ | `temporal_start_date` | `temporal` | Start of the temporal window, ISO 8601. Matches granules whose coverage overlaps it. |
| ✅ | `temporal_end_date` | `temporal` | End of the temporal window, ISO 8601. Matches granules whose coverage overlaps it. |
| ✅ | `spatial_wkt_geometry` | `polygon, point, bounding_box` | Area of interest as a WKT `POLYGON`, `POINT`, or `LINESTRING`. Matches granules whose footprint intersects it, so a precise shape avoids false positives. |
| ✅ | `cloud_cover_min` | `cloud_cover` | Lower bound on cloud cover, 0 to 100. Optical imagery only; SAR and altimetry do not report it. |
| ✅ | `cloud_cover_max` | `cloud_cover` | Upper bound on cloud cover, 0 to 100. Use `20` or lower for mostly clear scenes. Optical imagery only. |
| ✅ | `day_night_flag` | `day_night_flag` | Acquisition lighting, one of `DAY`, `NIGHT`, or `UNSPECIFIED`. |
| ✅ | `sort_key` | `sort_key` | Result ordering, e.g. `-start_date` for newest first. Defaults to relevance, not recency, so recent data is not returned first unless asked for. |
| ❌ | N/A | `granule_ur` | Search by exact granule UR |
| ❌ | N/A | `producer_granule_id` | Search by producer granule ID |
| ❌ | N/A | `readable_granule_name` | Search by either granule UR or producer ID |
| ❌ | N/A | `orbit_number` | Filter granules by orbit number |
| ❌ | N/A | `updated_since` | Filter by recently updated granules |

### Output Fields
| Status | MCP Response Field | UMM JSON Path | Transformed | Description |
|---|---|---|---|---|
| ✅ | `access_urls` | `RelatedUrls` | ✅ | Actionable data access URLs (Note: Access requires Earthdata Login authentication) |
| ✅ | `additional_attributes` | `AdditionalAttributes` | ✅ | Provider-specific attributes (e.g., tile coords, quality flags) — array of {name, values[]} |
| ✅ | `bounding_box` | `SpatialExtent.HorizontalSpatialDomain.Geometry.BoundingRectangles` | ✅ | `[West, South, East, North]` minimum bounding rectangle. Encloses swath and irregular footprints, so the corners may hold no data. |
| ✅ | `cloud_cover` | `CloudCover` | | Cloud cover percentage |
| ✅ | `collection_concept_id` | `CollectionReference.ShortName/Version` | | Parent collection concept ID |
| ✅ | `concept_id` | `meta.concept-id` | | CMR granule concept ID |
| ✅ | `data_format` | `DataFormat` | ✅ | File format (e.g., NetCDF-4, GeoTIFF) |
| ✅ | `day_night_flag` | `DataGranule.DayNightFlag` | | DAY, NIGHT, BOTH, or UNSPECIFIED |
| ✅ | `granule_ur` | `GranuleUR` | | Granule UR |
| ✅ | `native_id` | `meta.native-id` | | The native ID of the granule record |
| ✅ | `orbit_info` | `SpatialExtent.OrbitCalculatedSpatialDomains` | ✅ | Orbit calculated spatial domains — array of {orbit_number, equator_crossing_longitude, equator_crossing_date_time} |
| ✅ | `producer_granule_id` | `DataGranule.ProducerGranuleId` | | Producer granule ID |
| ✅ | `production_date` | `DataGranule.ProductionDateTime` | ✅ | Date the granule was generated (ProductionDateTime) |
| ✅ | `provider_id` | `meta.provider-id` | | The provider ID of the granule |
| ✅ | `revision_id` | `meta.revision-id` | | The revision ID of the granule metadata |
| ✅ | `size_mb` | `DataGranule.ArchiveAndDistributionInformation` | ✅ | Size of the data granule in MB |
| ✅ | `time_end` | `TemporalExtent.RangeDateTime.EndingDateTime` | ✅ | Granule temporal end |
| ✅ | `time_start` | `TemporalExtent.RangeDateTime.BeginningDateTime` | ✅ | Granule temporal start |
| ❌ | N/A | `AccessConstraints` | | Access constraints and authorization requirements |
| ❌ | N/A | `InputGranules` | | Provenance information about source granules |
| ❌ | N/A | `MeasuredParameters` | | Variables/parameters measured in the granule |
| ❌ | N/A | `Platforms` | | Specific platforms used for the granule |
| ❌ | N/A | `Projects` | | Projects or campaigns associated with the granule |

---

## `get_variables`
Discovers scientific variables and measurements associated with a collection, or looks up variables by keyword.
- **CMR Endpoint:** [`/search/variables`](https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html#variable-search)
- **Schema:** [UMM-V (v1.9.0)](https://cdn.earthdata.nasa.gov/umm/variable/v1.9.0)

### Input Parameters
| Status | MCP Argument | CMR API Parameter | Description |
|---|---|---|---|
| ✅ | `collection_concept_id` | `concept_id` | Collection to find variables for, e.g. `C2763266360-LPCLOUD`. |
| ✅ | `keyword` | `keyword` | Free-text keyword to discover variables without a collection ID. |
| ❌ | N/A | `name` | Exact match on variable name |
| ❌ | N/A | `provider` | Filter by provider ID |

### Output Fields
| Status | MCP Response Field | UMM JSON Path | Transformed | Description |
|---|---|---|---|---|
| ✅ | `concept_id` | `meta.concept-id` | | CMR variable concept ID |
| ✅ | `name` | `Name` | | The short name of the variable |
| ✅ | `long_name` | `LongName` | | The long name of the variable |
| ✅ | `definition` | `Definition` | | The definition of the variable |
| ✅ | `data_type` | `DataType` | | The data type of the variable |
| ✅ | `units` | `Units` | | The units of the variable |
| ✅ | `scale` | `Scale` | | The scale factor for the variable data |
| ✅ | `offset` | `Offset` | | The offset for the variable data |
| ✅ | `fill_values` | `FillValues` | | Fill values used for missing or invalid data |
| ✅ | `valid_ranges` | `ValidRanges` | | Valid data ranges for the variable |
| ✅ | `dimensions` | `Dimensions` | | Dimensions associated with the variable |
| ✅ | `standard_name` | `StandardName` | | The CF Standard Name of the variable |
| ✅ | `science_keywords` | `ScienceKeywords` | | GCMD Science Keywords hierarchy |
| ✅ | `variable_type` | `VariableType` | | Type of variable (e.g., SCIENCE_VARIABLE, COORDINATE) |
| ✅ | `variable_sub_type` | `VariableSubType` | | Sub-type of variable |
| ✅ | `sets` | `Sets` | | Logical groupings for the variable |
| ✅ | `measurement_identifiers` | `MeasurementIdentifiers` | | Measurement context and provenance |
| ✅ | `sampling_identifiers` | `SamplingIdentifiers` | | Sampling method context |
| ✅ | `related_urls` | `RelatedUrls` | ✅ | URLs specific to the variable |
| ❌ | N/A | `AdditionalIdentifiers` | | Additional identifiers for the variable |
| ❌ | N/A | `IndexRanges` | | Array index ranges for the variable |
| ❌ | N/A | `InstanceInformation` | | Variable instance information |

---

## `get_tools`
Finds web portals and downloadable software associated with a collection, returning URLs and deep-linking templates.
- **CMR Endpoint:** [`/search/tools`](https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html#tool-search)
- **Schema:** [UMM-T (v1.2.0)](https://cdn.earthdata.nasa.gov/umm/tool/v1.2.0)

### Input Parameters
| Status | MCP Argument | CMR API Parameter | Description |
|---|---|---|---|
| ✅ | `collection_concept_id` | `concept_id` | Collection to find associated tools for, e.g. `C2723758340-GES_DISC`. |
| ✅ | `keyword` | `keyword` | Free-text keyword to discover tools without a collection ID. |
| ❌ | N/A | `name` | Exact match on tool name |
| ❌ | N/A | `provider` | Filter by provider ID |

### Output Fields
| Status | MCP Response Field | UMM JSON Path | Transformed | Description |
|---|---|---|---|---|
| ✅ | `access_constraints` | `AccessConstraints` | | Constraints for accessing the tool |
| ✅ | `concept_id` | `meta.concept-id` | | CMR tool concept ID |
| ✅ | `description` | `Description` | | A brief description of the tool |
| ✅ | `doi` | `DOI` | | Digital Object Identifier of the tool |
| ✅ | `long_name` | `LongName` | | The long name of the tool |
| ✅ | `name` | `Name` | | The name of the tool |
| ✅ | `native_id` | `meta.native-id` | | The native ID of the tool record |
| ✅ | `organizations` | `Organizations` | | Organizations responsible for the tool |
| ✅ | `potential_action` | `PotentialAction` | | Smart handoff definition for parameterized deep links |
| ✅ | `provider_id` | `meta.provider-id` | | The provider ID of the tool |
| ✅ | `quality` | `Quality` | | Quality information about the tool |
| ✅ | `related_urls` | `RelatedUrls` | ✅ | Documentation, guides, or other related links |
| ✅ | `revision_id` | `meta.revision-id` | | The revision ID of the tool metadata |
| ✅ | `supported_browsers` | `SupportedBrowsers` | | Browsers and versions supported by the tool |
| ✅ | `supported_input_formats` | `SupportedInputFormats` | | List of input format names supported by the tool |
| ✅ | `supported_operating_systems` | `SupportedOperatingSystems` | | Operating systems and versions supported by the tool |
| ✅ | `supported_output_formats` | `SupportedOutputFormats` | | List of output format names supported by the tool |
| ✅ | `supported_software_languages` | `SupportedSoftwareLanguages` | | Programming languages and versions supported by the tool |
| ✅ | `tool_keywords` | `ToolKeywords` | | Earth science keywords representative of the tool |
| ✅ | `type` | `Type` | | The type of the tool (e.g., Downloadable Tool, Web User Interface, Web Portal, Model) |
| ✅ | `url` | `URL` | | Primary URL for accessing the tool |
| ✅ | `use_constraints` | `UseConstraints` | | Restrictions or limitations on using the tool |
| ✅ | `version` | `Version` | | The edition or version of the tool |
| ❌ | N/A | `AncillaryKeywords` | | Additional keywords for the tool |
| ❌ | N/A | `ContactGroups/ContactPersons` | | Point of contact information |
| ❌ | N/A | `LastUpdatedDate` | | When the tool metadata was last updated |

---

## `get_services`
Discovers data access endpoints and visualization layers associated with a collection.
- **CMR Endpoint:** [`/search/services`](https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html#service-search)
- **Schema:** [UMM-S (v1.5.3)](https://cdn.earthdata.nasa.gov/umm/service/v1.5.3)

### Input Parameters
| Status | MCP Argument | CMR API Parameter | Description |
|---|---|---|---|
| ✅ | `collection_concept_id` | `concept_id` | Collection to find associated services for, e.g. `C2723758340-GES_DISC`. |
| ✅ | `keyword` | `keyword` | Free-text keyword to discover services without a collection ID. |
| ✅ | `type` | `type` | Service type to filter by, e.g. `OPeNDAP`, `WMS`, `Harmony`. |
| ❌ | N/A | `name` | Exact match on service name |
| ❌ | N/A | `provider` | Filter by provider ID |

### Output Fields
| Status | MCP Response Field | UMM JSON Path | Transformed | Description |
|---|---|---|---|---|
| ✅ | `access_constraints` | `AccessConstraints` | | Authentication or authorization requirements |
| ✅ | `concept_id` | `meta.concept-id` | | CMR service concept ID |
| ✅ | `description` | `Description` | | A brief description of the service |
| ✅ | `long_name` | `LongName` | | The long name of the service |
| ✅ | `name` | `Name` | | The name of the service |
| ✅ | `native_id` | `meta.native-id` | | The native ID of the service record |
| ✅ | `operation_metadata` | `OperationMetadata` | | Operation names and distributed computing platform |
| ✅ | `provider_id` | `meta.provider-id` | | The provider ID of the service |
| ✅ | `related_urls` | `RelatedUrls` | ✅ | Documentation, guides, or other related links |
| ✅ | `revision_id` | `meta.revision-id` | | The revision ID of the service metadata |
| ✅ | `service_keywords` | `ServiceKeywords` | | Controlled vocabulary for service capability |
| ✅ | `service_options` | `ServiceOptions` | | Subset types, supported projections, output formats |
| ✅ | `service_organizations` | `ServiceOrganizations` | ✅ | Organizations that run the service endpoint |
| ✅ | `type` | `Type` | | The type of the service |
| ✅ | `url` | `URL` | | Primary endpoint URL information |
| ✅ | `use_constraints` | `UseConstraints` | | Legal restrictions or usage limits |
| ✅ | `version` | `Version` | | The edition or version of the service |
| ❌ | N/A | `AncillaryKeywords` | | Additional keywords for the service |
| ❌ | N/A | `ContactGroups/ContactPersons` | | Point of contact information |
| ❌ | N/A | `ServiceQuality` | | Information about service quality |

---

## `get_keywords`
Discovers official Earthdata scientific vocabulary terms to translate colloquial user inputs into precise search labels.
- **CMR Endpoint:** [`/search/keywords`](https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html#keyword-search)
- **Schema:** [KMS Concept (v2.0)](https://wiki.earthdata.nasa.gov/x/aYX0Gg)

### Input Parameters
| Status | MCP Argument | CMR API Parameter | Description |
|---|---|---|---|
| ✅ | `query` | `pattern` | Term to search for across KMS schemes, e.g. `moisture`. |
| ✅ | `scheme` | `keyword_scheme` | A single KMS scheme to search, e.g. `sciencekeywords`, `platforms`, `instruments`. Searches every scheme if omitted. [Full list](https://cmr.earthdata.nasa.gov/kms/concept_schemes). |

### Output Fields
| Status | MCP Response Field | UMM JSON Path | Transformed | Description |
|---|---|---|---|---|
| ✅ | `uuid` | `uuid` | | The unique UUID of the KMS concept |
| ✅ | `prefLabel` | `prefLabel` | | The preferred label of the KMS concept |
| ✅ | `scheme` | `scheme` | | The scheme the concept belongs to |
| ✅ | `definition` | `definition` | | The primary definition of the concept, if available |

---

## `get_citations`
Discovers citation records (publications, DOIs) associated with a collection, or looks up a citation directly by identifier.
- **CMR Endpoint:** [`/search/citations`](https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html#searching-for-citations)
- **Schema:** Citation (v1.0.0), a CMR generic document type. Citations have not been adopted into UMM yet, so there is no published schema to link.

Exactly one of `collection_concept_id` or `identifier` is required. Supplying both, or neither, is a validation error.

`collection_concept_id` is not a CMR citation search parameter. The tool first reads the collection record's citation associations, then searches citations by the concept IDs it found, so a collection with no associations returns no results without a second request.

### Input Parameters
| Status | MCP Argument | CMR API Parameter | Description |
|---|---|---|---|
| ✅ | `collection_concept_id` | `concept_id[]` | Collection to find citations for, e.g. `C2763266360-LPCLOUD`. Resolved through the collection's citation associations. |
| ✅ | `identifier` | `identifier` | DOI or other citation identifier, e.g. `10.24193/AWC2022_05`. Looks up a single citation directly. |
| ✅ | `provider` | `provider` | CMR provider that published the citation, e.g. `ESDIS`. Combines with a collection or identifier lookup. |
| ❌ | N/A | `name` | Search by citation name. Exact match, not free text. |
| ❌ | N/A | `title` | Search by title. Exact match, not free text. |
| ❌ | N/A | `year` | Filter by publication year |
| ❌ | N/A | `author-name` | Search by author name |
| ❌ | N/A | `author-orcid` | Search by author ORCID |
| ❌ | N/A | `container` | Search by container or journal name |
| ❌ | N/A | `type` | Search by citation type (e.g., journal-article, proceedings-article) |
| ❌ | N/A | `identifier-type` | Filter by identifier type (e.g., DOI) |
| ❌ | N/A | `resolution-authority` | Filter by the authority that resolves the identifier |
| ❌ | N/A | `relationship-type` | Filter by relationship to the cited work (e.g., Cites, Refers) |
| ❌ | N/A | `related-identifier` | Search by an identifier the citation relates to |
| ❌ | N/A | `related-identifier-with-type` | Search relationship and identifier as a pair (e.g., `Cites:10.5067/SAMPLE/DATA`) |
| ❌ | N/A | `concept-id` | Direct lookup by citation concept ID |
| ❌ | N/A | `native-id` | Lookup by native ID |
| ❌ | N/A | `id` | Lookup by citation ID |
| ❌ | N/A | `keyword` | Search by science keyword. Accepted by CMR but returns no matches for citation records. |

### Output Fields
Every field in the Citation schema is surfaced.

| Status | MCP Response Field | Record JSON Path | Transformed | Description |
|---|---|---|---|---|
| ✅ | `abstract` | `Abstract` | | Abstract or description of the cited work |
| ✅ | `associated_collections` | `meta.associations.collections` | ✅ | Concept IDs of collections this citation is associated with. Pass these to `get_collections` for the dataset details. |
| ✅ | `citation_metadata` | `CitationMetadata` | | Nested bibliographic metadata (Author, Year, Publisher, Title, Container, Volume, Pages, and related fields) |
| ✅ | `concept_id` | `meta.concept-id` | | CMR citation concept ID |
| ✅ | `identifier` | `Identifier` | | The primary identifier, usually a DOI |
| ✅ | `identifier_type` | `IdentifierType` | | Type of the identifier (e.g., DOI) |
| ✅ | `metadata_specification` | `MetadataSpecification` | | Schema name, version, and URL for the citation record |
| ✅ | `name` | `Name` | | The name or title of the citation |
| ✅ | `native_id` | `meta.native-id` | | The native ID of the citation record |
| ✅ | `provider_id` | `meta.provider-id` | | The provider ID of the citation |
| ✅ | `related_identifiers` | `RelatedIdentifiers` | | Related works and datasets, each with a relationship type (e.g., Cites, Refers) |
| ✅ | `resolution_authority` | `ResolutionAuthority` | | Authority that resolves the identifier (e.g., https://doi.org) |
| ✅ | `revision_id` | `meta.revision-id` | | The revision ID of the citation metadata |

---

## `get_transformation_options`
Looks up which Harmony operations a collection supports (subsetting, reprojection, averaging, concatenation), which services implement them, supported output formats, and variables.
- **Underlying API:** Harmony [`/capabilities`](https://github.com/nasa/harmony/blob/main/services/harmony/app/markdown/capabilities.md) endpoint
- **Response Format:** Capabilities response version 3 (pinned server-side; not exposed as a tool input)

### Input Parameters
| Status | MCP Argument | Harmony API Parameter | Description |
|---|---|---|---|
| ✅ | `collection_concept_id` | `collectionId` | Concept ID of the collection (format: C\<number\>-\<PROVIDER\>). Exactly one of `collection_id` or `short_name` must be provided. |
| ✅ | `short_name` | `shortName` | Short name of the collection. Exactly one of `collection_id` or `short_name` must be provided. If multiple collections share the short name, Harmony prefers the one configured for use in Harmony. |
| ❌ | N/A | `version` | Capabilities response format version — pinned to '3' server-side, not user-configurable |

### Output Fields
| Status | MCP Response Field | Harmony Capabilities Field | Transformed | Description |
|---|---|---|---|---|
| ✅ | `concept_id` | `conceptId` | | Concept ID of the collection |
| ✅ | `short_name` | `shortName` | | Short name of the collection |
| ✅ | `summary` | *(top-level capability fields)* | ✅ | Collection-level summary object combining: |
| ↳ | `summary.subsetting.bbox` | `subsetting.bbox` | | True if bounding box subsetting is supported |
| ↳ | `summary.subsetting.dimension` | `subsetting.dimension` | | True if dimension subsetting is supported |
| ↳ | `summary.subsetting.shape` | `subsetting.shape` | | True if shape (polygon) subsetting is supported |
| ↳ | `summary.subsetting.temporal` | `subsetting.temporal` | | True if temporal subsetting is supported |
| ↳ | `summary.subsetting.variable` | `subsetting.variable` | | True if variable subsetting is supported |
| ↳ | `summary.reprojection.supported` | `reprojection.supported` | | True if reprojection is supported |
| ↳ | `summary.reprojection.supported_projections` | `reprojection.supportedProjections` | ✅ | Output projections supported across applicable services — each with `name` and `crs` (e.g., 'EPSG:4326') |
| ↳ | `summary.reprojection.interpolation_methods` | `reprojection.interpolationMethods` | ✅ | Interpolation methods supported for resampling during reprojection |
| ↳ | `summary.averaging.time` | `averaging.time` | | True if time averaging is supported |
| ↳ | `summary.averaging.area` | `averaging.area` | | True if area averaging is supported |
| ↳ | `summary.concatenation` | `concatenation` | | True if concatenation is supported |
| ↳ | `summary.output_formats` | `outputFormats` | ✅ | Output formats supported across all applicable services — each with `name` and `mime_type` |
| ✅ | `services` | `services` | ✅ | Harmony services applicable to the collection, each with `name`, `href` (link to the service's UMM-S record in CMR), and a per-service `capabilities` object (same shape as `summary`) — some capability combinations are only valid on specific services, so check here to determine which combinations a given service supports |
| ✅ | `variables` | `variables` | ✅ | Variables associated with the collection, each with `name`, `long_name`, `href` (link to the variable's UMM-Var record in CMR), `units`, and `science_keywords` (GCMD Category/Topic/Term/VariableLevel1-3/DetailedVariable) |
| ✅ | `capabilities_version` | `capabilitiesVersion` | | Version identifier of this capabilities response format (currently pinned to '3') |

---

## `submit_transformation_job`
Submits a Harmony data processing request (subset/reformat/reproject).
- **Underlying Library:** [harmony-py](https://github.com/nasa/harmony-py) — `Request` + `Client.submit()`
- **Underlying Endpoint:** Harmony job submission API (OGC Coverages-based)

### Input Parameters
| Status | MCP Argument | harmony-py `Request` Parameter | Description |
|---|---|---|---|
| ✅ | `collection_concept_id` | `collection` (via `Collection(id=...)`) | CMR concept ID of the collection (e.g., C1234567-PROV). |
| ✅ | `bbox` | `spatial` (via `BBox(west, south, east, north)`) | Bounding box array in degrees: [west, south, east, north]. |
| ✅ | `shape` | `shape` | Local path to a supported Harmony shapefile-subsetting file (.zip/.shz/.json/.geojson/.kml). |
| ✅ | `temporal_start` / `temporal_stop` | `temporal` (dict: `{'start': ..., 'stop': ...}`) | ISO 8601 start/stop timestamps for temporal subsetting. |
| ✅ | `variables` | `variables` | List of specific variable names to subset. |
| ✅ | `format` | `format` | Desired output MIME type (e.g., 'image/tiff', 'application/x-netcdf4'). |
| ✅ | `crs` | `crs` | Target Coordinate Reference System for reprojection (e.g., 'EPSG:4326'). |
| ✅ | `width` | `width` | Target width in pixels for spatial reprojection/resampling. |
| ✅ | `height` | `height` | Target height in pixels for spatial reprojection/resampling. |
| ✅ | `max_results` | `max_results` | Maximum number of granules/results to process. |
| ✅ | `granule_ids` | `granule_id` | Optional list of specific CMR granule concept IDs to process. |
| ❌ | N/A | `concatenate` | Concatenate outputs into a single file |
| ❌ | N/A | `grid` | Named output grid |
| ❌ | N/A | `extend` | Dimension(s) to extend |
| ❌ | N/A | `average` | Spatial/temporal averaging method |
| ❌ | N/A | `skip_preview` | Skip generation of preview images |
| ❌ | N/A | `destination_url` | Custom output destination (e.g., user's own S3 bucket) |
| ❌ | N/A | `ignore_errors` | Continue job even if some granules fail |
| ❌ | N/A | `labels` | Job labels for organization/tracking |

### Output Fields
Same output model as [`get_transformation_job_status`](#get_transformation_job_status) below (`GetTransformationJobStatusOutput`) — see that section's Output Fields table for the full field list (`job_id`, `status`, `message`, `progress`, `created_at`/`updated_at`, `links`, `total_hits`, `next_cursor`, `code`, `description`, etc.). Immediately after submission, `status` typically reflects the job's initial state (e.g., `running` or `accepted`) rather than a terminal state, and `links` will typically be empty until the job completes. `code`/`description` are populated only if the submission itself failed.

---

## `get_transformation_job_status`
Gets the current status, progress percentage, and metadata for a Harmony job.
- **Underlying Library:** [harmony-py](https://github.com/nasa/harmony-py) — `Client.status()`
- **Underlying Endpoint:** Harmony `GET /jobs/{jobID}` API

> **Note:** Like other search tools, this tool also supports `limit`, `cursor`, and `fields` — but unlike CMR-backed tools, pagination here is applied **in-memory** to the job's `links` array after Harmony returns the full job record, rather than being passed through to an upstream API page parameter. Cursors are job-scoped and lock in the original `job_id`.

### Input Parameters
| Status | MCP Argument | harmony-py Parameter | Description |
|---|---|---|---|
| ✅ | `job_id` | `job_id` | The ID of the Harmony job to check. |
| ✅ | `limit` | N/A (in-memory slicing, MCP-side) | Max number of `links` to return per page (default 10). |
| ✅ | `cursor` | N/A (in-memory slicing, MCP-side) | Job-scoped pagination token over the `links` array. |
| ✅ | `fields` | N/A (MCP-side response filtering) | Restrict which output fields are returned. |

### Output Fields
| Status | MCP Response Field | harmony-py / Job JSON Field | Transformed | Description |
|---|---|---|---|---|
| ✅ | `job_id` | `jobID` | | Unique identifier (UUID) for the job |
| ✅ | `status` | `status` | | Current status (`running`, `successful`, `failed`, `canceled`, etc.) |
| ✅ | `message` | `message` | | Human-readable message regarding the job status |
| ✅ | `progress` | `progress` | | Progress percentage of the job (0–100) |
| ✅ | `created_at` | `createdAt` | | UTC timestamp (ISO 8601) when the job was created |
| ✅ | `updated_at` | `updatedAt` | | UTC timestamp (ISO 8601) when the job was last updated |
| ✅ | `created_at_local` | `createdAt` | ✅ | Local timestamp equivalent of `created_at` |
| ✅ | `updated_at_local` | `updatedAt` | ✅ | Local timestamp equivalent of `updated_at` |
| ✅ | `request` | `request` | | The original Harmony request URL with parameters |
| ✅ | `num_input_granules` | `numInputGranules` | | Total number of input granules processed by the job |
| ✅ | `data_expiration` | `dataExpiration` | | UTC timestamp (ISO 8601) when the job's data will expire |
| ✅ | `data_expiration_local` | `dataExpiration` | ✅ | Local timestamp equivalent of `data_expiration` |
| ✅ | `links` | `links` | ✅ | Result/download links for the current page, sliced in-memory from the full job link list once terminal |
| ✅ | `total_hits` | N/A (computed from full `links` count) | ✅ | Full link count for the job |
| ✅ | `next_cursor` | N/A (computed, MCP-side) | ✅ | Opaque, job-scoped pagination token for the next page of `links`; `None` when no more results |

---

## `control_transformation_job`
Cancels, pauses, or resumes a running or paused Harmony transformation job.
- **Underlying Library:** [harmony-py](https://github.com/nasa/harmony-py) — `Client.cancel()` / `Client.pause()` / `Client.resume()`, followed by `Client.status()`
- **Underlying Endpoint:** Harmony job control API (`PUT /jobs/{jobID}/cancel`, `/pause`, `/resume`)

> **Note — valid state transitions:** `resume` on a job that isn't paused, or `pause`/`cancel` on a job that's already in a terminal state (e.g., `successful`, `failed`, `canceled`), will return an error from Harmony. Callers are encouraged to check `get_transformation_job_status` first if the job's current state is uncertain.

### Input Parameters
| Status | MCP Argument | harmony-py Parameter | Description |
|---|---|---|---|
| ✅ | `job_id` | `job_id` | The ID of the Harmony job to control. |
| ✅ | `action` | N/A (dispatches to `cancel()` / `pause()` / `resume()`) | One of `"cancel"`, `"pause"`, or `"resume"`. |

### Output Fields
Same output model as [`get_transformation_job_status`](#get_transformation_job_status) (`GetTransformationJobStatusOutput`) — see that section's Output Fields table for the full field list (`job_id`, `status`, `message`, `progress`, `created_at`/`updated_at`, `links`, `total_hits`, `next_cursor`, `code`, `description`, etc.). The returned `status` reflects the job's state **immediately after** the requested action is applied (e.g., `canceled`, `paused`, `running`), not a final/terminal outcome if the action triggers further async processing. `code`/`description` are populated if input validation fails, if the control action itself fails (e.g., invalid state transition), or if Harmony's status response doesn't match the expected schema.
