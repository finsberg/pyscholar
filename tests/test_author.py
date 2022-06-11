import factory
import pyscholar


def test_author_diff_with_one_new():
    author_old = factory.AuthorFactory.build()
    new_pub = factory.PublicationFactory.build()
    author_new = pyscholar.Author(
        name=author_old.name,
        scholar_id=author_old.scholar_id,
        publications=author_old.publications + (new_pub,),
    )
    new_pubs = pyscholar.author.author_pub_diff(author_new, author_old)
    assert len(new_pubs) == 1
    assert new_pubs[0] == new_pub


def test_author_diff_with_one_new_and_one_new_old():
    author_old = factory.AuthorFactory.build()
    new_pub = factory.PublicationFactory.build()
    old_new_pub = factory.PublicationFactory.build()
    author_new = pyscholar.Author(
        name=author_old.name,
        scholar_id=author_old.scholar_id,
        publications=author_old.publications + (new_pub,),
    )
    author_old = pyscholar.Author(
        name=author_old.name,
        scholar_id=author_old.scholar_id,
        publications=author_old.publications + (old_new_pub,),
    )
    new_pubs = pyscholar.author.author_pub_diff(author_new, author_old)
    assert len(new_pubs) == 1
    assert new_pubs[0] == new_pub
