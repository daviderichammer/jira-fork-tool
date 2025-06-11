# Jira API Research Findings

## Jira REST API Overview

### API Versions
- **REST API v3**: Latest version for Jira Cloud platform (current focus)
- **REST API v2**: Previous version, still available
- **Server/Data Center APIs**: Different endpoints for on-premise installations

### Key API Capabilities
- Full programmatic access to Jira functionality
- Resource expansion for optimized responses
- Pagination support for large datasets
- Ordering and filtering capabilities
- Support for both authenticated and anonymous access (where permitted)

### Authentication Methods
- **Forge apps**: REST API scopes for authentication
- **Connect apps**: App user permissions + required scopes
- **Direct API access**: Requires appropriate user permissions

### Permission Requirements
Most operations require specific permissions:
- **Administer the Cloud site**: Site-admins group
- **Administer Jira**: Jira Administrators global permission
- **Administer a project**: Administer projects project permission
- **Access a project**: Browse projects project permission
- **Access Jira**: Jira Users global permission

### API Structure
- Base URL: `/rest/api/3/<resource-name>`
- Example: `/rest/api/3/issue/DEMO-1`
- Supports expansion, pagination, and ordering
- JSON responses with metadata

## Next Research Areas
- Issue creation and numbering constraints
- Bulk operations and rate limits
- Attachment and comment handling
- Authentication token setup



## Authentication Methods

### Basic Authentication (Recommended for Scripts)
- **Method**: Email + API Token
- **Security**: Less secure than OAuth but suitable for scripts
- **Setup**: Generate API token from Atlassian account
- **Format**: `Authorization: Basic <base64(email:api_token)>`
- **Example**: `curl -u fred@example.com:api_token`

### OAuth 2.0 (3LO) - Most Secure
- **Method**: OAuth 2.0 authorization code grants
- **Security**: Most secure option
- **Use case**: Production integrations
- **Setup**: Create app in developer console

### Forge Apps
- **Method**: Built-in OAuth 2.0
- **Security**: High security, built into framework
- **Scopes**: REST API scopes required

### Connect Apps
- **Method**: JWT-based authentication
- **Security**: High security
- **Setup**: Built into Connect framework

### API Token Generation
1. Access Atlassian Account settings
2. Generate API token
3. Use email:token combination for basic auth
4. Benefits:
   - Works with 2FA enabled
   - Can be revoked individually
   - More secure than passwords

### Security Considerations
- CAPTCHA triggered after failed attempts
- Same permissions as web interface
- Anonymous access available for public resources
- Authentication challenges not provided by default


## Issue Creation and Numbering Constraints

### Critical Limitation: Issue Number Control
**MAJOR FINDING**: Jira REST API does NOT allow setting custom issue numbers during creation.

Key points from research:
- Issue numbers are automatically assigned by Jira's internal counter
- No REST API parameter exists to specify issue key numbers
- Even Java API setNumber() method doesn't work for controlling issue numbers
- Jira determines the next free number automatically
- Issue numbers are NOT guaranteed to be sequential (gaps can occur)

### Bulk Operations Available
- **Bulk Delete**: Up to 1,000 issues per operation
- **Bulk Edit**: Multiple field updates across issues
- **Bulk Move**: Transfer issues between projects
- **Bulk Transition**: Change status of multiple issues
- **Rate Limiting**: Only 5 concurrent bulk requests allowed

### Implications for Fork Tool
This creates a significant challenge for maintaining synchronized ticket numbers:

1. **Cannot directly control issue numbers** - Must use alternative strategy
2. **Must create issues sequentially** - To minimize gaps
3. **Need gap detection and handling** - Create placeholder/dummy issues for gaps
4. **Requires custom field tracking** - Store original issue numbers as metadata

### Alternative Synchronization Strategies
1. **Sequential Creation with Gap Handling**:
   - Read source issues in order (1, 2, 3, ...)
   - Create destination issues sequentially
   - For gaps in source, create placeholder issues in destination
   - Delete placeholders or mark as "deleted/migrated"

2. **Custom Field Mapping**:
   - Store original issue key in custom field
   - Use for cross-referencing and linking
   - Maintain mapping table for lookups

3. **Project Counter Manipulation** (Server only):
   - Direct database access to reset project counter
   - Not available in Cloud instances
   - Requires administrative access


## Attachments and Comments Handling

### Attachment Operations
Available REST API endpoints:
- **GET** `/rest/api/3/attachment/{id}` - Get attachment metadata
- **GET** `/rest/api/3/attachment/content/{id}` - Download attachment content
- **POST** `/rest/api/3/issue/{issueIdOrKey}/attachments` - Add attachment to issue
- **DELETE** `/rest/api/3/attachment/{id}` - Delete attachment
- **GET** `/rest/api/3/attachment/thumbnail/{id}` - Get thumbnail
- **GET** `/rest/api/3/attachment/meta` - Get attachment settings

Key features:
- Support for HTTP Range header for partial downloads
- Thumbnail generation available
- Anonymous access possible for public attachments
- File upload via multipart/form-data
- Requires `X-Atlassian-Token: no-check` header for uploads

### Comment Operations
Available REST API endpoints:
- **GET** `/rest/api/3/issue/{issueIdOrKey}/comment` - Get all comments for issue
- **POST** `/rest/api/3/issue/{issueIdOrKey}/comment` - Add comment
- **GET** `/rest/api/3/issue/{issueIdOrKey}/comment/{id}` - Get specific comment
- **PUT** `/rest/api/3/issue/{issueIdOrKey}/comment/{id}` - Update comment
- **DELETE** `/rest/api/3/issue/{issueIdOrKey}/comment/{id}` - Delete comment
- **POST** `/rest/api/3/comment/list` - Get comments by IDs (bulk)

Key features:
- Supports Atlassian Document Format (ADF) for rich text
- Visibility restrictions (roles, groups)
- Pagination support for large comment lists
- Anonymous access for public comments
- Comment properties for metadata

### Data Migration Considerations

#### Attachment Migration Strategy:
1. **Download from source**: Use content endpoint to download files
2. **Store temporarily**: Save to local filesystem or cloud storage
3. **Upload to destination**: Use attachment POST endpoint
4. **Preserve metadata**: Filename, author, creation date
5. **Handle large files**: Use streaming for memory efficiency

#### Comment Migration Strategy:
1. **Preserve formatting**: Convert between text formats if needed
2. **Maintain authorship**: Map user accounts between systems
3. **Preserve timestamps**: Store original creation/update dates
4. **Handle visibility**: Map role/group restrictions
5. **Maintain threading**: Preserve comment order and relationships

#### Challenges:
- **User mapping**: Source and destination users may differ
- **Permission mapping**: Role/group structures may not match
- **File size limits**: Attachment size restrictions
- **Rate limiting**: API call frequency restrictions
- **Format conversion**: Different rich text formats between versions


## Rate Limiting and Best Practices

### Rate Limiting Implementation
Jira uses a sophisticated rate limiting system based on:

#### Cost and Counter Based Limits
- **User budget**: Requests made by end users
- **App budget**: Requests made by apps without user interaction  
- **App + user budget**: Requests made by apps with user interaction
- **Anonymous budget**: Unauthenticated requests

#### Quota and Burst Limits
- **Burst period**: 10 seconds
- **Quota period**: 1 hour
- Rules consider app, tenant, request count, product edition, and user count

### Rate Limit Detection and Handling
- **HTTP 429**: Rate limit exceeded
- **Retry-After header**: Seconds to wait before retry
- **X-RateLimit-Reset**: Timestamp when limit resets
- **X-RateLimit-Remaining**: Requests remaining in window
- **X-RateLimit-NearLimit**: Warning when <20% budget remains

### Best Practices for Fork Tool

#### Request Optimization:
1. **Use App + User context** for scalability
2. **Implement exponential backoff** with jitter
3. **Batch operations** where possible
4. **Cache responses** to reduce API calls
5. **Use pagination** efficiently

#### Error Handling:
1. **Monitor 429 responses** and implement retry logic
2. **Respect Retry-After headers**
3. **Implement circuit breakers** for failing endpoints
4. **Log rate limit events** for monitoring

#### Scaling Considerations:
- Design for "App + user" budget to scale with user count
- Avoid "App" budget for user-initiated actions
- Consider tenant size when planning sync operations

### API Token Rate Limits (Effective Nov 22, 2025)
- New rate limits will be implemented for API tokens
- Review and optimize request costs before implementation
- Consider migration to OAuth 2.0 for better scaling

### Bulk Operation Limits
- Maximum 1,000 issues per bulk delete operation
- Only 5 concurrent bulk requests allowed
- Rate limits apply to all bulk operations

### Recommendations for Fork Tool:
1. **Implement progressive sync** with rate limit awareness
2. **Use bulk operations** where available
3. **Monitor rate limit headers** proactively
4. **Implement queue-based processing** with backoff
5. **Consider time-based sync windows** to spread load

