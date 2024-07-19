"""Implementation of the compass API."""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Any, Literal, overload

import requests

from foundry_dev_tools.clients.api_client import APIClient
from foundry_dev_tools.errors.compass import (
    FolderNotFoundError,
    ResourceNotFoundError,
)
from foundry_dev_tools.errors.handling import ErrorHandlingConfig, raise_foundry_api_error
from foundry_dev_tools.utils import api_types
from foundry_dev_tools.utils.api_types import assert_in_literal

if TYPE_CHECKING:
    from collections.abc import Iterator

GET_PATHS_BATCH_SIZE = 100
GET_PROJECTS_BATCH_SIZE = 1

DEFAULT_PROJECTS_PAGE_SIZE = 100
MINIMUM_PROJECTS_PAGE_SIZE = 1
MAXIMUM_PROJECTS_PAGE_SIZE = 500
MINIMUM_PROJECTS_SEARCH_OFFSET = 0
MAXIMUM_PROJECTS_SEARCH_OFFSET = 500


@overload
def get_decoration(
    decoration: api_types.ResourceDecorationSetAll | None,
    conv: Literal[False],
) -> api_types.ResourceDecorationSet | None: ...


@overload
def get_decoration(
    decoration: api_types.ResourceDecorationSetAll | None,
    conv: Literal[True],
) -> list[api_types.ResourceDecoration] | None: ...


@overload
def get_decoration(
    decoration: api_types.ResourceDecorationSetAll | None,
    conv: Literal[True] = ...,
) -> list[api_types.ResourceDecoration] | None: ...


def get_decoration(
    decoration: api_types.ResourceDecorationSetAll | None,
    conv: bool = True,
) -> list[api_types.ResourceDecoration] | api_types.ResourceDecorationSet | None:
    """Parses the decoration argument used by the compass client methods."""
    if decoration == "all":
        return list(api_types.ALL_RESOURCE_DECORATIONS) if conv else api_types.ALL_RESOURCE_DECORATIONS
    return None if decoration is None else (list(decoration) if conv else decoration)


class CompassClient(APIClient):
    """CompassClient class that implements methods from the 'compass' API."""

    api_name = "compass"

    def api_get_resource(
        self,
        rid: api_types.Rid,
        decoration: api_types.ResourceDecorationSetAll | None = None,
        permissive_folders: bool | None = None,
        additional_operations: set[str] | None = None,
        **kwargs,
    ) -> requests.Response:
        """Gets the resource of the resource identifier.

        Args:
            rid: the identifier of the resource
            decoration: extra decoration entries in the response
            permissive_folders: if true read permissions are not needed if not in hidden folder
            additional_operations: include extra operations in result if user has the operation
            **kwargs: gets passed to :py:meth:`APIClient.api_request`
        """
        params = {"decoration": get_decoration(decoration)}
        if permissive_folders is not None:
            params["permissiveFolders"] = permissive_folders  # type: ignore[assignment]
        if additional_operations is not None:
            params["additionalOperations"] = additional_operations  # type: ignore[assignment]
        return self.api_request(
            "GET",
            f"resources/{rid}",
            params=params,
            error_handling=ErrorHandlingConfig(api_error_mapping={204: ResourceNotFoundError}),
            **kwargs,
        )

    def api_get_resource_by_path(
        self,
        path: api_types.FoundryPath,
        decoration: api_types.ResourceDecorationSetAll | None = None,
        permissive_folders: bool | None = None,
        additional_operations: set[str] | None = None,
        **kwargs,
    ) -> requests.Response:
        """Gets the resource of the path.

        Args:
            path: the path of the resource
            decoration: extra decoration entries in the response
            permissive_folders: if true read permissions are not needed if not in hidden folder
            additional_operations: include extra operations in result if user has the operation
            **kwargs: gets passed to :py:meth:`APIClient.api_request`
        """
        params = {"path": path, "decoration": get_decoration(decoration)}
        if permissive_folders is not None:
            params["permissiveFolders"] = permissive_folders  # type: ignore[assignment]
        if additional_operations is not None:
            params["additionalOperations"] = additional_operations  # type: ignore[assignment]
        return self.api_request(
            "GET",
            "resources",
            params=params,
            error_handling=ErrorHandlingConfig(api_error_mapping={204: ResourceNotFoundError}, path=path),
            **kwargs,
        )

    def api_check_name(
        self,
        parent_folder_rid: api_types.Rid,
        name: str | None = None,
        **kwargs,
    ) -> requests.Response:
        """Check if parent folder contains a child resource with the given name.

        Args:
            parent_folder_rid: the resource identifier of the parent folder that is checked
            name: the name to be checked
            **kwargs: gets passed to :py:meth:`APIClient.api_request`

        Returns:
            response:
                the response contains a json which is a bool,
                indicating whether the resource name already exists or not
        """
        body = {}

        if name is not None:
            body["name"] = name

        return self.api_request(
            "POST",
            f"resources/{parent_folder_rid}/checkName",
            json=body,
            error_handling=ErrorHandlingConfig({"Compass:NotFound": FolderNotFoundError}),
            **kwargs,
        )

    def api_add_to_trash(
        self,
        rids: set[api_types.Rid],
        user_bearer_token: str | None = None,
        **kwargs,
    ) -> requests.Response:
        """Add resource to trash.

        Args:
            rids: set of resource identifiers
            user_bearer_token: bearer token, needed when dealing with service project resources
            **kwargs: gets passed to :py:meth:`APIClient.api_request`
        """
        response = self.api_request(
            "POST",
            "batch/trash/add",
            headers={"User-Bearer-Token": f"Bearer {user_bearer_token}"} if user_bearer_token else None,
            json=list(rids),
            **kwargs,
        )
        if response.status_code != requests.codes.no_content:
            raise_foundry_api_error(
                response,
                ErrorHandlingConfig(info="Issue while moving resource(s) to trash.", rids=rids),
            )
        return response

    def api_restore(
        self,
        rids: set[api_types.Rid],
        user_bearer_token: str | None = None,
        **kwargs,
    ) -> requests.Response:
        """Restore resource from trash.

        Args:
            rids: set of resource identifiers
            user_bearer_token: bearer token, needed when dealing with service project resources
            **kwargs: gets passed to :py:meth:`APIClient.api_request`
        """
        response = self.api_request(
            "POST",
            "batch/trash/restore",
            headers={"User-Bearer-Token": f"Bearer {user_bearer_token}"} if user_bearer_token else None,
            json=list(rids),
            **kwargs,
        )
        if response.status_code != requests.codes.no_content:
            raise_foundry_api_error(response, ErrorHandlingConfig(info="Issue while restoring resource(s) from trash."))
        return response

    def api_delete_permanently(
        self,
        rids: set[api_types.Rid],
        delete_options: set[Literal["DO_NOT_REQUIRE_TRASHED", "DO_NOT_TRACK_PERMANENTLY_DELETED_RIDS"]] | None = None,
        user_bearer_token: str | None = None,
        **kwargs,
    ) -> requests.Response:
        """Permanently deletes a Resource.

        Args:
            rids: set of resource identifiers
            delete_options: delete options, self explanatory
            user_bearer_token: bearer token, needed when dealing with service project resources
            **kwargs: gets passed to :py:meth:`APIClient.api_request`
        """
        return self.api_request(
            "POST",
            "trash/delete",
            headers={"User-Bearer-Token": f"Bearer {user_bearer_token}"} if user_bearer_token else None,
            params={"deleteOptions": list(delete_options) if delete_options else None},
            json=list(rids),
            **kwargs,
        )

    def api_create_folder(
        self,
        name: str,
        parent_id: api_types.Rid,
        marking_ids: set[str] | None = None,
        **kwargs,
    ) -> requests.Response:
        """Creates an empty folder in compass.

        Args:
            name: name of the new folder
            parent_id: rid of the parent folder,
                e.g. ri.compass.main.folder.aca0cce9-2419-4978-bb18-d4bc6e50bd7e
            marking_ids: marking IDs
            **kwargs: gets passed to :py:meth:`APIClient.api_request`

        Returns:
            response:
                which contains a json:
                    with keys rid and name and other properties.

        """
        json: dict[str, str | set] = {"name": name, "parentId": parent_id}
        if marking_ids:
            json["markingIds"] = marking_ids
        return self.api_request(
            "POST",
            "folders",
            json=json,
            **kwargs,
        )

    def api_get_path(self, rid: api_types.Rid, **kwargs) -> requests.Response:
        """Returns the compass path for the rid."""
        kwargs.setdefault("error_handling", ErrorHandlingConfig(rid=rid))
        return self.api_request(
            "GET",
            f"resources/{rid}/path-json",
            **kwargs,
        )

    def api_get_paths(self, resource_ids: list[api_types.Rid], **kwargs) -> requests.Response:
        """Get paths for RIDs.

        Args:
            resource_ids: The identifiers of resources
            **kwargs: gets passed to :py:meth:`APIClient.api_request`

        """
        return self.api_request(
            "POST",
            "batch/paths",
            json=resource_ids,
            **kwargs,
        )

    def get_paths(
        self,
        resource_ids: list[api_types.Rid],
    ) -> dict[api_types.Rid, api_types.FoundryPath]:
        """Returns a dict which maps RIDs to Paths.

        Args:
            resource_ids: The identifiers of resources

        Returns:
            dict:
                mapping between rid and path
        """
        list_len = len(resource_ids)
        if list_len < GET_PATHS_BATCH_SIZE:
            batches = [resource_ids]
        else:
            batches = [resource_ids[i : i + GET_PATHS_BATCH_SIZE] for i in range(0, list_len, GET_PATHS_BATCH_SIZE)]
        result: dict[api_types.Rid, api_types.FoundryPath] = {}
        for batch in batches:
            result = {**result, **self.api_get_paths(batch).json()}
        return result

    def api_get_children(
        self,
        rid: api_types.Rid,
        filter: set[str] | None = None,  # noqa: A002
        decoration: api_types.ResourceDecorationSetAll | None = None,
        limit: int | None = None,
        sort: str | None = None,
        page_token: str | None = None,
        permissive_folders: bool | None = None,
        include_operations: bool = False,
        additional_operations: str | None = None,
    ) -> requests.Response:
        """Returns children in a given compass folder.

        Args:
            rid: resource identifier
            filter: filter out resources, syntax "service.instance.type"
            decoration: extra information for the decorated resource
            limit: maximum items in a page
            sort: A space-delimited specifier of the form "[a][ b]"
                 [a] can be "name", "lastModified", or "rid"
                 [b] is optional and can be "asc" or "desc"
                 (e.g. "rid asc", "name", "lastModified desc")
            page_token: start position for request
            permissive_folders: Allows folder access if any sub-resource is accessible, ignoring folder permissions
                Default is false, non-hidden folders only
            include_operations: Controls inclusion of Compass GK operations
                Is set to false in Foundry DevTools to improve performance. Set to `None` for Foundry instance default
            additional_operations: Adds specific user-permitted operations to response. Requires include_perations=True

        """
        return self.api_request(
            "GET",
            f"folders/{rid}/children",
            params={
                "filter": filter,
                "decoration": get_decoration(decoration),
                "limit": limit,
                "sort": sort,
                "pageToken": page_token,
                "permissiveFolders": permissive_folders,
                "includeOperations": include_operations,
                "additionalOperations": additional_operations,
            },
            error_handling=ErrorHandlingConfig({"Compass:NotFound": FolderNotFoundError}),
        )

    def get_child_objects_of_folder(
        self,
        rid: api_types.Rid,
        filter: set[str] | None = None,  # noqa: A002
        decoration: api_types.ResourceDecorationSetAll | None = None,
        limit: int | None = None,
        sort: str | None = None,
        permissive_folders: bool | None = None,
        include_operations: bool = False,
        additional_operations: str | None = None,
    ) -> Iterator[dict]:
        """Returns children in a given compass folder (automatic pagination).

        Args:
            rid: resource identifier
            filter: filter out resources, syntax "service.instance.type"
            decoration: extra information for the decorated resource
            limit: maximum items in a page
            sort: A space-delimited specifier of the form "[a][ b]"
                 [a] can be "name", "lastModified", or "rid"
                 [b] is optional and can be "asc" or "desc"
                 (e.g. "rid asc", "name", "lastModified desc")
            permissive_folders: Allows folder access if any sub-resource is accessible, ignoring folder permissions
                Default is false, non-hidden folders only
            include_operations: Controls inclusion of Compass GK operations
                Is set to false in Foundry DevTools to improve performance. Set to `None` for Foundry instance default
            additional_operations: Adds specific user-permitted operations to response. Requires include_perations=True

        """
        page_token = None
        while True:
            response_as_json = self.api_get_children(
                rid=rid,
                filter=filter,
                decoration=decoration,
                limit=limit,
                sort=sort,
                page_token=page_token,
                permissive_folders=permissive_folders,
                include_operations=include_operations,
                additional_operations=additional_operations,
            ).json()
            yield from response_as_json["values"]
            if (page_token := response_as_json["nextPageToken"]) is None:
                break

    def api_get_resources(
        self,
        rids: set[api_types.Rid],
        decoration: api_types.ResourceDecorationSetAll | None = None,
        include_operations: bool = False,
        additional_operations: set[str] | None = None,
    ) -> requests.Response:
        """Returns the resources for the RIDs.

        Args:
            rids: the resource identifiers
            decoration: extra information to add to the result
            include_operations: Controls inclusion of Compass GK operations.
                Is set to false in Foundry DevTools to improve performance. Set to `None` for Foundry instance default.
            additional_operations: Adds specific user-permitted operations to response. Requires include_perations=True.
        """
        return self.api_request(
            "POST",
            "batch/resources",
            params={
                "decoration": get_decoration(decoration),
                "includeOperations": include_operations,
                "additionalOperations": list(additional_operations) if additional_operations is not None else None,
            },
            json=list(rids),
        )

    def api_process_marking(
        self,
        rid: api_types.Rid,
        marking_id: api_types.MarkingId,
        path_operation_type: api_types.PatchOperation,
        user_bearer_token: str | None = None,
        **kwargs,
    ) -> requests.Response:
        """Process marking to add or remove from resource.

        Args:
            rid: resource identifier of the resource for which a marking is adjusted
            marking_id: The id of the marking to be used
            path_operation_type: path operation type, see :py:class:`api_types.PatchOperation`
            user_bearer_token: bearer token, needed when dealing with service project resources
            **kwargs: gets passed to :py:meth:`APIClient.api_request`
        """
        assert_in_literal(path_operation_type, api_types.PatchOperation, "path_operation_type")

        body = {"markingPatches": [{"markingId": marking_id, "patchOperation": path_operation_type}]}

        return self.api_request(
            "POST",
            f"markings/{rid}",
            headers={"User-Bearer-Token": f"Bearer {user_bearer_token}"} if user_bearer_token else None,
            json=body,
            **kwargs,
        )

    def add_marking(
        self,
        rid: api_types.Rid,
        marking_id: api_types.MarkingId,
        user_bearer_token: str | None = None,
    ) -> requests.Response:
        """Add marking to resource.

        Args:
            rid: resource identifier of the resource for which a marking will be added
            marking_id: The id of the marking to be added
            user_bearer_token: bearer token, needed when dealing with service project resources
        """
        return self.api_process_marking(rid, marking_id, "ADD", user_bearer_token)

    def remove_marking(
        self,
        rid: api_types.Rid,
        marking_id: api_types.MarkingId,
        user_bearer_token: str | None = None,
    ) -> requests.Response:
        """Remove marking from resource.

        Args:
            rid: resource identifier of the resource for which a marking will be removed
            marking_id: The id of the marking to be removed
            user_bearer_token: bearer token, needed when dealing with service project resources
        """
        return self.api_process_marking(rid, marking_id, "REMOVE", user_bearer_token)

    def api_add_imports(
        self,
        project_rid: api_types.ProjectRid,
        rids: set[api_types.Rid],
        user_bearer_token: str | None = None,
        **kwargs,
    ) -> requests.Response:
        """Add reference to a project via import.

        Args:
            project_rid: resource identifier of the project
            rids: set of resource identifiers of the resources being imported
            user_bearer_token: bearer token, needed when dealing with service project resources
            **kwargs: gets passed to :py:meth:`APIClient.api_request`
        """
        body = {"requests": [{"resourceRid": rid} for rid in rids]}

        return self.api_request(
            "POST",
            f"projects/imports/{project_rid}/import",
            headers={"User-Bearer-Token": f"Bearer {user_bearer_token}"} if user_bearer_token else None,
            json=body,
            **kwargs,
        )

    def api_remove_imports(
        self,
        project_rid: api_types.ProjectRid,
        rids: set[api_types.Rid],
        user_bearer_token: str | None = None,
        **kwargs,
    ) -> requests.Response:
        """Remove imported reference from a project.

        Args:
            project_rid: resource identifier of the project
            rids: set of resource identifiers of the resources that will be removed from import
            user_bearer_token: bearer token, needed when dealing with service project resources
            **kwargs: gets passed to :py:meth:`APIClient.api_request`
        """
        body = {"resourceRid": rids}

        return self.api_request(
            "DELETE",
            f"projects/imports/{project_rid}/import",
            headers={"User-Bearer-Token": f"Bearer {user_bearer_token}"} if user_bearer_token else None,
            json=body,
            **kwargs,
        )

    def api_set_name(
        self,
        rid: api_types.Rid,
        name: str,
        **kwargs,
    ) -> requests.Response:
        """Remove imported reference from a project.

        Args:
            rid: resource identifier of the resource whose name will be changed
            name: The resource name that should be set
            **kwargs: gets passed to :py:meth:`APIClient.api_request`
        """
        body = {"name": name}

        return self.api_request(
            "POST",
            f"resources/{rid}/name",
            json=body,
            **kwargs,
        )

    def api_resources_exist(
        self,
        rids: set[api_types.Rid],
        **kwargs,
    ) -> requests.Response:
        """Check if resources exist.

        Args:
            rids: set of resource identifiers to check whether they exist
            **kwargs: gets passed to :py:meth:`APIClient.api_request`

        Returns:
            dict:
                with key-value pairs, where the key is the rid of the checked resource
                and the value indicates whether the resource exists or not.
        """
        return self.api_request(
            "POST",
            "batch/resources/exist",
            json=list(rids),
            **kwargs,
        )

    def resources_exist(self, rids: set[api_types.Rid]) -> dict[api_types.Rid, bool]:
        """Check if resources exist.

        Args:
            rids: set of resource identifiers to check whether they exist

        Returns:
            dict:
                mapping between rid and bool as indicator for resource existence
        """
        return self.api_resources_exist(rids).json()

    def resource_exists(
        self,
        rid: api_types.Rid,
    ) -> bool:
        """Check if resource exists.

        Args:
            rid: resource identifier of resource to check whether it exists

        Returns:
            bool:
                true if resource exists, false otherwise
        """
        result = self.resources_exist({rid})

        return result.get(rid, False)

    def api_get_projects_by_rids(self, rids: list[api_types.ProjectRid], **kwargs) -> requests.Response:
        """Fetch projects by their resource identifiers.

        Args:
            rids: list of project resource identifiers that shall be fetched
            **kwargs: gets passed to :py:meth:`APIClient.api_request`

        Returns:
            response:
                which contains a json dict:
                    with project information about every project
        """
        return self.api_request(
            "PUT",
            "hierarchy/v2/batch/projects",
            json=rids,
            **kwargs,
        )

    def get_projects_by_rids(
        self,
        rids: list[api_types.ProjectRid],
    ) -> dict[api_types.ProjectRid, dict[str, Any]]:
        """Returns a dict which maps rids to projects.

        Args:
            rids: list of project resource identifiers that shall be fetched

        Returns:
            dict:
                mapping between rid and project
        """
        list_len = len(rids)
        if list_len < GET_PATHS_BATCH_SIZE:
            batches = [rids]
        else:
            batches = [rids[i : i + GET_PATHS_BATCH_SIZE] for i in range(0, list_len, GET_PROJECTS_BATCH_SIZE)]

        result: dict[api_types.FolderRid, dict[str, Any]] = {}
        for batch in batches:
            result.update(self.api_get_projects_by_rids(batch).json())

        return result

    def get_project_by_rid(
        self,
        rid: api_types.ProjectRid,
    ) -> dict[str, Any] | None:
        """Returns a single project.

        Args:
            rid: resource identifier of a project to be fetched

        Returns:
            dict:
                mapping of project attribute keys and their respective values
        """
        result = self.api_get_projects_by_rids([rid]).json()

        return result.get(rid)

    def api_resolve_path(self, path: api_types.FoundryPath, **kwargs) -> requests.Response:
        """Fetch all resources that are part of the path string.

        Args:
            path: path: the path of the resource
            **kwargs: gets passed to :py:meth:`APIClient.api_request`

        Returns:
            response:
                the response contains a json which is a list of resources representing the path components
        """
        return self.api_request(
            "GET",
            "paths",
            params={"path": path},
            **kwargs,
        )

    def api_search_projects(
        self,
        query: str | None = None,
        decorations: api_types.ResourceDecorationSetAll | None = None,
        organizations: set[api_types.Rid] | None = None,
        tags: set[api_types.Rid] | None = None,
        roles: set[api_types.RoleId] | None = None,
        include_home_projects: bool | None = None,
        direct_role_grant_principal_ids: dict[str, set[api_types.RoleId]] | None = None,
        sort: api_types.SortSpec | None = None,
        page_size: int = DEFAULT_PROJECTS_PAGE_SIZE,
        page_token: str | None = None,
        **kwargs,
    ) -> requests.Response:
        """Returns a list of projects satisfying the search criteria.

        Args:
            query: search term for the project
            decorations: extra information for the decorated resource
            organizations: queries only for organizations with these marking identifiers
            tags: only includes projects with these tags
            roles: filters for projects where the user has one of the roles
            include_home_projects: whether to consider home projects of the user
            direct_role_grant_principal_ids:  only return projects for which the role identifiers
                for given principal identifiers have been granted
            sort: see :py:meth:`foundry_dev_tools.utils.api_types.Sort`
            page_size: the maximum number of projects to return. Must be in the range 0 < N <= 500
            page_token: start position for request. Must be in the range 0 <= N <= 500
            **kwargs: gets passed to :py:meth:`APIClient.api_request`

        Returns:
            response:
                the response contains a json which is a dict with a list of projects
                and an optional nextPageToken in case all the projects could not be fetched all at once

        Raises:
            ValueError: When `page_token` is in inappropriate format. Should be a number in the range 0 <= N <= 500.

        """
        if decorations is not None:
            decorations = get_decoration(decorations)

        if page_size < MINIMUM_PROJECTS_PAGE_SIZE:
            warnings.warn(
                f"Parameter `page_size` ({page_size}) is less than "
                f"the minimum page size ({MINIMUM_PROJECTS_PAGE_SIZE}). "
                f"Defaulting to {MINIMUM_PROJECTS_PAGE_SIZE}."
            )
            page_size = MINIMUM_PROJECTS_PAGE_SIZE
        elif page_size > MAXIMUM_PROJECTS_PAGE_SIZE:
            warnings.warn(
                f"Parameter `page_size` ({page_size}) is greater than "
                f"the maximum page size ({MAXIMUM_PROJECTS_PAGE_SIZE}). "
                f"Defaulting to {MAXIMUM_PROJECTS_SEARCH_OFFSET}."
            )
            page_size = MAXIMUM_PROJECTS_PAGE_SIZE

        if page_token is not None:
            if page_token.isdecimal() is False:
                msg = (
                    f"Parameter `page_token` ({page_token}) is expected to contain a number "
                    f"as the starting offset for the request. "
                    f"The search offset must be within the range from "
                    f"{MINIMUM_PROJECTS_SEARCH_OFFSET} to {MAXIMUM_PROJECTS_SEARCH_OFFSET}."
                )
                raise ValueError(msg)

            page_token_int = int(page_token)
            if page_token_int < MINIMUM_PROJECTS_SEARCH_OFFSET:
                msg = (
                    f"Parameter `page_token` ({page_token_int}) is less than "
                    f"the minimum search offset ({MINIMUM_PROJECTS_SEARCH_OFFSET})"
                )
                raise ValueError(msg)
            if page_token_int > MAXIMUM_PROJECTS_SEARCH_OFFSET:
                msg = (
                    f"Parameter `page_token` ({page_token_int}) is greater than "
                    f"the maximum search offset ({MAXIMUM_PROJECTS_SEARCH_OFFSET})"
                )
                raise ValueError(msg)

        body = {
            "query": query,
            "decorations": decorations,
            "organizations": organizations,
            "tags": tags,
            "roles": roles,
            "includeHomeProjects": include_home_projects,
            "directRoleGrantPrincipalIds": direct_role_grant_principal_ids,
            "sort": sort,
            "pageSize": page_size,
            "pageToken": page_token,
        }

        return self.api_request(
            "POST",
            "search/projects",
            json=body,
            **kwargs,
        )

    def search_projects(
        self,
        query: str | None = None,
        decorations: api_types.ResourceDecorationSetAll | None = None,
        organizations: set[api_types.Rid] | None = None,
        tags: set[api_types.Rid] | None = None,
        roles: set[api_types.RoleId] | None = None,
        include_home_projects: bool | None = None,
        direct_role_grant_principal_ids: dict[str, set[api_types.RoleId]] | None = None,
        sort: api_types.SortSpec | None = None,
        page_size: int = DEFAULT_PROJECTS_PAGE_SIZE,
    ) -> Iterator[dict]:
        """Returns a list of projects satisfying the search criteria (automatic pagination).

        Args:
            query: search term for the project
            decorations: extra information for the decorated resource
            organizations: queries only for organizations with these marking identifiers
            tags: only includes projects with these tags
            roles: filters for projects where the user has one of the roles
            include_home_projects: whether to consider home projects of the user
            direct_role_grant_principal_ids:  only return projects for which the role identifiers
                for given principal identifiers have been granted
            sort: see :py:meth:`foundry_dev_tools.utils.api_types.Sort`
            page_size: the maximum number of projects to return. Must be in the range 0 < N <= 500

        Returns:
            Iterator[dict]:
                which contains the project data as a dict
        """
        page_token = None
        while True:
            response_as_json = self.api_search_projects(
                query=query,
                decorations=decorations,
                organizations=organizations,
                tags=tags,
                roles=roles,
                include_home_projects=include_home_projects,
                direct_role_grant_principal_ids=direct_role_grant_principal_ids,
                sort=sort,
                page_size=page_size,
                page_token=page_token,
            ).json()
            yield from response_as_json["values"]

            page_token = response_as_json["nextPageToken"]
            if page_token is None or (int(page_token) > MAXIMUM_PROJECTS_PAGE_SIZE):
                break

    def api_get_resource_roles(
        self,
        rids: set[api_types.Rid],
        **kwargs,
    ) -> requests.Response:
        """Retrieve the role grants for a set of resources.

        Args:
            rids: set of resource identifiers, for the resources for which the role grants should be returned
            **kwargs: gets passed to :py:meth:`APIClient.api_request`

        Returns:
            response:
                which consists of a json returning a mapping between resource identifier and the associated grants
        """
        body = {"rids": list(rids)}

        return self.api_request("POST", "roles", json=body, **kwargs)

    def get_resource_roles(
        self,
        rids: set[api_types.Rid],
    ) -> dict[api_types.Rid, api_types.ResourceGrantsResult]:
        """Returns a mapping between resource identifier and resource grants result.

        Args:
            rids: set of resource identifiers, for the resources for which the role grants should be returned
        """
        return self.api_get_resource_roles(rids).json()

    def api_update_resource_roles(
        self,
        rid: api_types.Rid,
        grant_patches: set[api_types.RoleGrantPatch] | None = None,
        disable_inherited_permissions_for_principals: set[api_types.UserGroupPrincipalPatch] | None = None,
        disable_inherited_permissions: bool | None = None,
        **kwargs,
    ) -> requests.Response:
        """Updates the role grants for a resource.

        Args:
            rid: resource identifier, for the resource for which roles will be updated
            grant_patches: the role grants that should be patched
            disable_inherited_permissions_for_principals: patch role grants for the provided inherited permissions
            disable_inherited_permissions: disable inherited permissions
            **kwargs: gets passed to :py:meth:`APIClient.api_request`
        """
        body = {}

        if grant_patches is not None:
            body["grantPatches"] = grant_patches
        if disable_inherited_permissions_for_principals is not None:
            body["disableInheritedPermissionsForPrincipals"] = disable_inherited_permissions_for_principals
        if disable_inherited_permissions is not None:
            body["disableInheritedPermissions"] = disable_inherited_permissions

        return self.api_request(
            "POST",
            f"roles/v2/{rid}",
            json=body,
            **kwargs,
        )
