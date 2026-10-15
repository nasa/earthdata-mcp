---
title: Supported Parameters
head:
  - tag: style
    content: ':root { --sl-content-width: 70rem; }'
---

This reference maps Earthdata MCP tool parameters to the upstream API arguments and schema fields behind them. It provides consumers with a clear picture of current API integration depth and search capabilities. Each tool's section names the endpoint and schema it is built on.

<terra-alert open variant="information" appearance="subtle">
	<terra-icon slot="icon" name="solid-information-circle" library="heroicons"></terra-icon>
	All search tools globally support the <strong>limit</strong>, <strong>cursor</strong>, and <strong>fields</strong> parameters for pagination and response filtering. These are omitted from the tables below for brevity.
</terra-alert>

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
| ✅ | `platform` | `platform` | Platform short names to filter by (e.g., ['Terra', 'Aqua']). Most common scientific filter after temporal/spatial. |
| ✅ | `instrument` | `instrument` | Instrument short names to filter by (e.g., ['MODIS', 'VIIRS']). More precise than keyword for instrument filtering. |
| ✅ | `processing_level_id` | `processing_level_id` | Processing levels to filter by, e.g. `3`, `3A`. Distinguishes L2 swath from L3 gridded products. |
| ✅ | `has_granules` | `has_granules` | When True, filters to collections that have actual granule data. Prevents returning metadata-only shells. |
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
| ✅ | `day_night_flag` | `day_night_flag` | Filter granules by day/night acquisition flag. Values: 'DAY', 'NIGHT', 'UNSPECIFIED'. |
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
| ✅ | `collection_concept_id` | `concept_id` | The CMR concept ID of the collection to find variables for (e.g., 'C12345-PROV'). |
| ✅ | `keyword` | `keyword` | A free-text search keyword to find variables. |
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
| ✅ | `collection_concept_id` | `concept_id` | Parent collection concept ID. |
| ✅ | `keyword` | `keyword` | Free-text keyword. |
| ✅ | `type` | `type` | Filter by service type. |
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
| ✅ | `query` | `pattern` | The term to search for across KMS schemes (e.g. 'moisture'). |
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
| ✅ | `identifier` | `identifier` | A DOI or other citation identifier used to look up a citation directly (e.g., 10.24193/AWC2022_05). |
| ✅ | `provider` | `provider` | Restricts results to citations from a single CMR provider (e.g., ESDIS). Combines with either of the above. |
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
