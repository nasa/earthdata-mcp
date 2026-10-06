# Earthdata MCP Parameter Support Reference

This reference maps Earthdata MCP tool parameters to their corresponding CMR API arguments and underlying UMM schema paths. It provides consumers with a clear picture of current API integration depth and search capabilities.

## Table of Contents
- [`get_collections`](#get_collections)
- [`get_granules`](#get_granules)
- [`get_variables`](#get_variables)
- [`get_tools`](#get_tools)
- [`get_services`](#get_services)
- [`get_keywords`](#get_keywords)
- [`get_citations`](#get_citations) (Needs documentation)
- **Harmony Transformation Tools**
- [`get_transformation_options`](#get_transformation_options)
- [`submit_transformation_job`](#submit_transformation_job)
- [`get_transformation_job_status`](#get_transformation_job_status)
- [`control_transformation_job`](#control_transformation_job)

> **Note:** All search tools globally support the `limit`, `cursor`, and `fields` parameters for pagination and response filtering. These are omitted from the tables below for brevity.

> **Note on Harmony tools:** Unlike the CMR-backed tools above, the four Harmony transformation tools below do not query CMR's `/search` endpoints or use UMM schemas. They call the [Harmony](https://harmony.earthdata.nasa.gov/) API directly via the official [harmony-py](https://github.com/nasa/harmony-py) client library. Parameter/field tables for these tools reference harmony-py and the Harmony API's own JSON response shapes instead of CMR API parameters and UMM JSON paths. All four share a common `BaseHarmonyToolOutput` base model contributing `code` and `description` fields, populated only when a request fails.
>
> **Authentication required:** Unlike the CMR-backed discovery tools, all four Harmony tools require an authenticated Earthdata Login access token (retrieved via `get_access_token()`) to call Harmony's API on the user's behalf.

---

### `get_collections`
Searches for datasets (collections) using scientific keywords, instruments, platforms, or spatial/temporal constraints.
- **CMR Endpoint:** [`/search/collections`](https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html#collection-search)
- **Schema:** [UMM-C (v1.18.3)](https://cdn.earthdata.nasa.gov/umm/collection/v1.18.3)

#### Input Parameters
| Status | MCP Argument | CMR API Parameter | Description |
|---|---|---|---|
| ✅ | `keyword` | `keyword` | Free-text keyword search. Case insensitive. IMPORTANT — CMR uses AND logic: each space-separated word is matched independently and ALL words must appear somewhere in a collection's indexed fields (title, summary, short name, GCMD science keywords, platform and instrument names, project names, processing level, archive centers, additional attributes, etc.). Words do NOT need to appear in the same field or as a contiguous phrase. Because every word must match, adding more words makes the search STRICTER, not broader — the opposite of typical web search engines. Prefer 2–4 precise terms over long queries. Example: 'soil moisture' (2 terms, broad) vs 'soil moisture SMAP L3' (4 terms, narrow). Phrase search: wrap the entire value in escaped double quotes to require an exact phrase (e.g., '\"sea surface temperature\"'). Only a single phrase is supported; you cannot mix a phrase with additional standalone words. Wildcards supported: * (zero or more chars), ? (any single char). Use scientific terms: geophysical variable names ('sea surface temperature', 'soil moisture'), instrument names (MODIS, ASCAT, VIIRS, AIRS, Landsat, etc.), or platform names (Terra, Aqua, SMAP, Sentinel-1, etc.). For known product short names use the short_name parameter instead. |
| ✅ | `concept_id` | `concept_id` | Exact CMR concept ID (format: C<number>-<PROVIDER>, e.g., C2036882064-POCLOUD). Use for direct lookup of a known collection. |
| ✅ | `short_name` | `short_name` | Collection short name (e.g., MOD11A1, SPL3SMP, MUR-JPL-L4-GLOB-v4.1). Exact match by default; wildcards * and ? are supported. |
| ✅ | `provider` | `provider` | Data provider short name (e.g., PODAAC, NSIDC_ECS, GES_DISC, ORNL_DAAC, LAADS, GHRC_DAAC, ASDC). Restricts results to collections from that provider. WARNING: NASA DAACs are actively migrating assets to the cloud under new provider IDs (e.g., LPDAAC_ECS → LPCLOUD, PODAAC → POCLOUD). If you know the exact short_name of a product, do NOT include the provider parameter — a stale provider ID will silently return 0 results. Use provider only when the user explicitly filters by archive center. |
| ✅ | `temporal_start_date` | `temporal` | Start of temporal filter in ISO 8601 format (e.g., 2020-01-01T00:00:00Z). Restricts results to collections whose declared temporal range overlaps this window. Set this whenever the user specifies a time period — omitting it returns collections regardless of when their data was collected. |
| ✅ | `temporal_end_date` | `temporal` | End of temporal filter in ISO 8601 format (e.g., 2020-12-31T23:59:59Z). Restricts results to collections whose declared temporal range overlaps this window. Set this whenever the user specifies a time period — omitting it returns collections regardless of when their data was collected. |
| ✅ | `spatial_wkt_geometry` | `polygon, point, bounding_box` | Spatial filter as WKT geometry. Supported types: POLYGON((lon lat, ...)), POINT(lon lat), or LINESTRING(lon lat, ...). Restricts results to collections whose declared extent intersects this area. CMR returns any collection that touches this shape, so precise geometries are preferred to prevent false positives. Set this whenever the user specifies a geographic region — omitting it returns collections with global or unspecified coverage. |
| ✅ | `platform` | `platform` | Platform short names to filter by (e.g., ['Terra', 'Aqua']). Most common scientific filter after temporal/spatial. |
| ✅ | `instrument` | `instrument` | Instrument short names to filter by (e.g., ['MODIS', 'VIIRS']). More precise than keyword for instrument filtering. |
| ✅ | `processing_level_id` | `processing_level_id` | Processing level IDs to filter by (e.g., ['3', '3A']). Essential for choosing between L2 swath and L3 gridded products. |
| ✅ | `has_granules` | `has_granules` | When True, filters to collections that have actual granule data. Prevents returning metadata-only shells. |
| ❌ | N/A | `doi` | Search by digital object identifier |
| ❌ | N/A | `project` | Search by project/campaign name |
| ❌ | N/A | `data_center` | Search by data center/archive center |
| ❌ | N/A | `science_keywords` | Search by GCMD science keywords hierarchy |
| ❌ | N/A | `updated_since` | Filter by recently updated collections |

#### Output Fields
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

### `get_granules`
Searches for specific data files (granules) within a collection to verify actual data availability for a given time and location.
- **CMR Endpoint:** [`/search/granules`](https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html#granule-search)
- **Schema:** [UMM-G (v1.6.5)](https://cdn.earthdata.nasa.gov/umm/granule/v1.6.5)

#### Input Parameters
| Status | MCP Argument | CMR API Parameter | Description |
|---|---|---|---|
| ✅ | `collection_concept_id` | `collection_concept_id` | Parent collection concept ID (format: C<number>-<PROVIDER>, e.g., C2723758340-GES_DISC). Required to scope granule search. |
| ✅ | `temporal_start_date` | `temporal` | Start of temporal filter in ISO 8601 format (e.g., 2024-01-01T00:00:00Z). Finds granules whose temporal extent overlaps this window. Set this whenever the user specifies a time period — omitting it returns granules from the entire collection archive regardless of date. |
| ✅ | `temporal_end_date` | `temporal` | End of temporal filter in ISO 8601 format (e.g., 2024-01-31T23:59:59Z). Finds granules whose temporal extent overlaps this window. Set this whenever the user specifies a time period — omitting it returns granules from the entire collection archive regardless of date. |
| ✅ | `spatial_wkt_geometry` | `polygon, point, bounding_box` | Spatial filter as WKT geometry. Supported types: POLYGON((lon lat, ...)), POINT(lon lat), or LINESTRING(lon lat, ...). Finds granules with spatial extent intersecting this area. CMR returns any granule that touches this shape, so precise geometries are preferred to prevent false positives. Set this whenever the user specifies a geographic region — omitting it returns granules from the entire globe regardless of location. |
| ✅ | `cloud_cover_min` | `cloud_cover` | Minimum cloud cover percentage (0–100, inclusive). Use with cloud_cover_max to filter optical/visible imagery granules by cloud cover. Only applicable to collections that report cloud cover (e.g., Landsat, MODIS, etc). Omit for non-optical data (SAR, altimetry, etc.). |
| ✅ | `cloud_cover_max` | `cloud_cover` | Maximum cloud cover percentage (0–100, inclusive). Use with cloud_cover_min to filter optical/visible imagery granules by cloud cover. For example, set cloud_cover_max=20 to find mostly clear scenes. Only applicable to collections that report cloud cover (e.g., Landsat, MODIS, etc). Omit for non-optical data (SAR, altimetry, etc.). |
| ✅ | `day_night_flag` | `day_night_flag` | Filter granules by day/night acquisition flag. Values: 'DAY', 'NIGHT', 'UNSPECIFIED'. |
| ✅ | `sort_key` | `sort_key` | Sort key for granule results. e.g., '-start_date' (newest first), 'start_date' (oldest first). CMR default is relevance score. For ongoing or near-real-time (NRT) missions where the user wants the most recent data, always use '-start_date' — CMR's default relevance scoring may return historical data first if sort_key is not explicitly set. |
| ❌ | N/A | `granule_ur` | Search by exact granule UR |
| ❌ | N/A | `producer_granule_id` | Search by producer granule ID |
| ❌ | N/A | `readable_granule_name` | Search by either granule UR or producer ID |
| ❌ | N/A | `orbit_number` | Filter granules by orbit number |
| ❌ | N/A | `updated_since` | Filter by recently updated granules |

#### Output Fields
| Status | MCP Response Field | UMM JSON Path | Transformed | Description |
|---|---|---|---|---|
| ✅ | `access_urls` | `RelatedUrls` | ✅ | Actionable data access URLs (Note: Access requires Earthdata Login authentication) |
| ✅ | `additional_attributes` | `AdditionalAttributes` | ✅ | Provider-specific attributes (e.g., tile coords, quality flags) — array of {name, values[]} |
| ✅ | `bounding_box` | `SpatialExtent.HorizontalSpatialDomain.Geometry.BoundingRectangles` | ✅ | [West, South, East, North] Minimum Bounding Rectangle (MBR). Note: For swath data or irregular polygons, this bounding box fully encloses the data but may contain empty space at the corners. |
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

### `get_variables`
Discovers scientific variables and measurements associated with a collection, or looks up variables by keyword.
- **CMR Endpoint:** [`/search/variables`](https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html#variable-search)
- **Schema:** [UMM-V (v1.9.0)](https://cdn.earthdata.nasa.gov/umm/variable/v1.9.0)

#### Input Parameters
| Status | MCP Argument | CMR API Parameter | Description |
|---|---|---|---|
| ✅ | `collection_concept_id` | `concept_id` | The CMR concept ID of the collection to find variables for (e.g., 'C12345-PROV'). |
| ✅ | `keyword` | `keyword` | A free-text search keyword to find variables. |
| ❌ | N/A | `name` | Exact match on variable name |
| ❌ | N/A | `provider` | Filter by provider ID |

#### Output Fields
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

### `get_tools`
Finds web portals and downloadable software associated with a collection, returning URLs and deep-linking templates.
- **CMR Endpoint:** [`/search/tools`](https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html#tool-search)
- **Schema:** [UMM-T (v1.2.0)](https://cdn.earthdata.nasa.gov/umm/tool/v1.2.0)

#### Input Parameters
| Status | MCP Argument | CMR API Parameter | Description |
|---|---|---|---|
| ✅ | `collection_concept_id` | `concept_id` | Parent collection concept ID (format: C<number>-<PROVIDER>, e.g., C2723758340-GES_DISC). When provided, searches for tools associated with this collection. |
| ✅ | `keyword` | `keyword` | Free-text keyword to discover tools without a collection ID. |
| ❌ | N/A | `name` | Exact match on tool name |
| ❌ | N/A | `provider` | Filter by provider ID |

#### Output Fields
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

### `get_services`
Discovers data access endpoints and visualization layers associated with a collection.
- **CMR Endpoint:** [`/search/services`](https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html#service-search)
- **Schema:** [UMM-S (v1.5.3)](https://cdn.earthdata.nasa.gov/umm/service/v1.5.3)

#### Input Parameters
| Status | MCP Argument | CMR API Parameter | Description |
|---|---|---|---|
| ✅ | `collection_concept_id` | `concept_id` | Parent collection concept ID. |
| ✅ | `keyword` | `keyword` | Free-text keyword. |
| ✅ | `type` | `type` | Filter by service type. |
| ❌ | N/A | `name` | Exact match on service name |
| ❌ | N/A | `provider` | Filter by provider ID |

#### Output Fields
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

### `get_keywords`
Discovers official Earthdata scientific vocabulary terms to translate colloquial user inputs into precise search labels.
- **CMR Endpoint:** [`/search/keywords`](https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html#keyword-search)
- **Schema:** [KMS Concept (v2.0)](https://wiki.earthdata.nasa.gov/display/CMR/KMS+2.0+User%27s+Guide)

#### Input Parameters
| Status | MCP Argument | CMR API Parameter | Description |
|---|---|---|---|
| ✅ | `query` | `pattern` | The term to search for across KMS schemes (e.g. 'moisture'). |
| ✅ | `scheme` | `keyword_scheme` | Optional. A single KMS scheme to narrow the search (e.g., 'sciencekeywords', 'platforms', 'instruments', 'projects', 'providers', 'locations'). If omitted, searches across all schemes globally. A complete list of valid scheme names can be fetched from https://cmr.earthdata.nasa.gov/kms/concept_schemes |

#### Output Fields
| Status | MCP Response Field | UMM JSON Path | Transformed | Description |
|---|---|---|---|---|
| ✅ | `uuid` | `uuid` | | The unique UUID of the KMS concept |
| ✅ | `prefLabel` | `prefLabel` | | The preferred label of the KMS concept |
| ✅ | `scheme` | `scheme` | | The scheme the concept belongs to |
| ✅ | `definition` | `definition` | | The primary definition of the concept, if available |

---

### `get_transformation_options`
Looks up which Harmony operations a collection supports (subsetting, reprojection, averaging, concatenation), which services implement them, supported output formats, and variables.
- **Underlying API:** Harmony [`/capabilities`](https://github.com/nasa/harmony/blob/main/services/harmony/app/markdown/capabilities.md) endpoint
- **Response Format:** Capabilities response version 3 (pinned server-side; not exposed as a tool input)

#### Input Parameters
| Status | MCP Argument | Harmony API Parameter | Description |
|---|---|---|---|
| ✅ | `collection_concept_id` | `collectionId` | Concept ID of the collection (format: C\<number\>-\<PROVIDER\>). Exactly one of `collection_id` or `short_name` must be provided. |
| ✅ | `short_name` | `shortName` | Short name of the collection. Exactly one of `collection_id` or `short_name` must be provided. If multiple collections share the short name, Harmony prefers the one configured for use in Harmony. |
| ❌ | N/A | `version` | Capabilities response format version — pinned to '3' server-side, not user-configurable |

#### Output Fields
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
| ✅ | `code` | *(from Harmony error response)* | | Error code if the request failed (inherited from `BaseHarmonyToolOutput`) |
| ✅ | `description` | *(from Harmony error response)* | | Error description if the request failed (inherited from `BaseHarmonyToolOutput`) |

---

### `submit_transformation_job`
Submits a Harmony data processing request (subset/reformat/reproject).
- **Underlying Library:** [harmony-py](https://github.com/nasa/harmony-py) — `Request` + `Client.submit()`
- **Underlying Endpoint:** Harmony job submission API (OGC Coverages-based)

#### Input Parameters
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

#### Output Fields
Same output model as [`get_transformation_job_status`](#get_transformation_job_status) below (`GetTransformationJobStatusOutput`, which itself extends `BaseHarmonyToolOutput`) — see that section's Output Fields table for the full field list (`job_id`, `status`, `message`, `progress`, `created_at`/`updated_at`, `links`, `total_hits`, `next_cursor`, `code`, `description`, etc.). Immediately after submission, `status` typically reflects the job's initial state (e.g., `running` or `accepted`) rather than a terminal state, and `links` will typically be empty until the job completes. `code`/`description` are populated only if the submission itself failed.

---

### `get_transformation_job_status`
Gets the current status, progress percentage, and metadata for a Harmony job.
- **Underlying Library:** [harmony-py](https://github.com/nasa/harmony-py) — `Client.status()`
- **Underlying Endpoint:** Harmony `GET /jobs/{jobID}` API

> **Note:** Like other search tools, this tool also supports `limit`, `cursor`, and `fields` — but unlike CMR-backed tools, pagination here is applied **in-memory** to the job's `links` array after Harmony returns the full job record, rather than being passed through to an upstream API page parameter. Cursors are job-scoped and lock in the original `job_id`.

#### Input Parameters
| Status | MCP Argument | harmony-py Parameter | Description |
|---|---|---|---|
| ✅ | `job_id` | `job_id` | The ID of the Harmony job to check. |
| ✅ | `limit` | N/A (in-memory slicing, MCP-side) | Max number of `links` to return per page (default 10). |
| ✅ | `cursor` | N/A (in-memory slicing, MCP-side) | Job-scoped pagination token over the `links` array. |
| ✅ | `fields` | N/A (MCP-side response filtering) | Restrict which output fields are returned. |

#### Output Fields
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
| ✅ | `code` | *(from Harmony error response)* | | Error code if the request failed (inherited from `BaseHarmonyToolOutput`) |
| ✅ | `description` | *(from Harmony error response)* | | Error description if the request failed (inherited from `BaseHarmonyToolOutput`) |

---

### `control_transformation_job`
Cancels, pauses, or resumes a running or paused Harmony transformation job.
- **Underlying Library:** [harmony-py](https://github.com/nasa/harmony-py) — `Client.cancel()` / `Client.pause()` / `Client.resume()`, followed by `Client.status()`
- **Underlying Endpoint:** Harmony job control API (`PUT /jobs/{jobID}/cancel`, `/pause`, `/resume`)

> **Note — valid state transitions:** `resume` on a job that isn't paused, or `pause`/`cancel` on a job that's already in a terminal state (e.g., `successful`, `failed`, `canceled`), will return an error from Harmony. Callers are encouraged to check `get_transformation_job_status` first if the job's current state is uncertain.

#### Input Parameters
| Status | MCP Argument | harmony-py Parameter | Description |
|---|---|---|---|
| ✅ | `job_id` | `job_id` | The ID of the Harmony job to control. |
| ✅ | `action` | N/A (dispatches to `cancel()` / `pause()` / `resume()`) | One of `"cancel"`, `"pause"`, or `"resume"`. |

#### Output Fields
Same output model as [`get_transformation_job_status`](#get_transformation_job_status) (`GetTransformationJobStatusOutput`, which itself extends `BaseHarmonyToolOutput`) — see that section's Output Fields table for the full field list (`job_id`, `status`, `message`, `progress`, `created_at`/`updated_at`, `links`, `total_hits`, `next_cursor`, `code`, `description`, etc.). The returned `status` reflects the job's state **immediately after** the requested action is applied (e.g., `canceled`, `paused`, `running`), not a final/terminal outcome if the action triggers further async processing. `code`/`description` are populated if input validation fails, if the control action itself fails (e.g., invalid state transition), or if Harmony's status response doesn't match the expected schema.