from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command

from ombucore.assets.models import ImageAsset
from website.help.models import HelpPage, HelpTopic


def get_help_body():
    return f"""
    <p>Dioptra will walk you through the process of entering 
    monitoring and finance data, and breaking down both program 
    and support costs, so you can see how much it costs to deliver services to your clients.</p>
    
    <div data-ombuimage="{{&quot;objInfo&quot;:{{&quot;id&quot;:1,&quot;title&quot;:&quot;Build Image&quot;,&quot;ctype_id&quot;:{ContentType.objects.get_for_model(ImageAsset).id},&quot;verbose_name&quot;:&quot;Image&quot;,&quot;verbose_name_plural&quot;:&quot;Images&quot;,&quot;change_url&quot;:&quot;/panels/assets/imageasset/1/change/&quot;,&quot;preview_url&quot;:&quot;/panels/assets/imageasset/1/preview/&quot;,&quot;width&quot;:&quot;1510&quot;,&quot;image_url&quot;:&quot;/media/help-page-rte-image.png&quot;}},&quot;caption&quot;:&quot;Ship of the imagination in a cosmic arena courage of our questions vastness is bearable only through love with pretty stories for which there's little good evidence inconspicuous motes of rock and gas&quot;,&quot;align&quot;:&quot;center&quot;}}"><img src="/media/help-page-rte-image.png" /><span class="caption" style="display:block">Ship of the imagination in a cosmic arena courage of our questions vastness is bearable only through love with pretty stories for which there&#39;s little good evidence inconspicuous motes of rock and gas</span></div>
    
    <h3>How do I know if I&#39;m ready?</h3>
    
    <ol>
      <li>Know the purpose of your cost analysis.</li>
      <li>Define the <em>program and output.</em></li>
      <li>Monitor <a href="/">output data.</a></li>
      <li><strong>Monitor cost data.</strong></li>
    </ol>
    
    <hr />
    <h4>Defining Outputs &amp; Time Frame for a Dioptra Analysis</h4>
    
    <ul>
      <li>Choose an intervention/output to analyze.</li>
      <li>Define the time frame to study.</li>
      <li>You do not need to analyze every intervention on a particular grant.</li>
    </ul>
    
    <h5>Table 1: Consumption expenditures by category</h5>
    
    <table>
      <thead>
        <tr>
          <th scope="col">CONSUMPTION</th>
          <th scope="col">CONTROL</th>
          <th scope="col">TUUNGANE</th>
          <th scope="col">N</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>Food</td>
          <td>40.48</td>
          <td>-1.9</td>
          <td>3,194</td>
        </tr>
        <tr>
          <td>Medical</td>
          <td>20.43</td>
          <td>-1.15</td>
          <td>3,334</td>
        </tr>
        <tr>
          <td>Leisure</td>
          <td>1.02</td>
          <td>-0.32</td>
          <td>3,374</td>
        </tr>
        <tr>
          <td>Clothes</td>
          <td>7.26</td>
          <td>-0.58</td>
          <td>3,386</td>
        </tr>
        <tr>
          <td>Alcohol</td>
          <td>2.94</td>
          <td>-0.52</td>
          <td>3,323</td>
        </tr>
      </tbody>
    </table>
    
    <p><a class="btn btn-primary" href="/">Proceed to Dioptra</a></p>
    
    <p><a class="btn btn-secondary" href="/grants/">Grant information</a></p>
    
    """


blank_pages = (
    ("How do I define the time frame or the outputs of my program?", "General"),
    ("How do I gather the information I need for Dioptra analysis?", "General"),
    ("Defining an Analysis", "Analysis"),
    ("Loading Data in an Analysis", "Analysis"),
    ("Confirming Cost Items with Categories", "Analysis"),
    ("Allocating the Percentage of Costs Towards an Intervention", "Analysis"),
    ("How to Use Insights", "Analysis"),
    ("About Cost Drivers and Applying Strategies", "Using Dioptra results"),
    ("Economies of Scale", "Using Dioptra results"),
    ("Targeting Methods", "Using Dioptra results"),
    ("Scale of Training", "Using Dioptra results"),
    ('Program "Scale" is Limited Context', "Using Dioptra results"),
    ("Help Article Name Medium Long", "Dioptra in Action"),
    ("Help Article Name", "Dioptra in Action"),
    ("Help Article Name Long Lorem Ipsum Dolor Sit Danimal", "Dioptra in Action"),
    ("Help Article Name", "Accounts and Permissions"),
    ("Another Help Article Name", "Dioptra in Action"),
    ("Help Article Name Medium Long", "Accounts and Permissions"),
    ("Help Article Name", "Accounts and Permissions"),
)


def build_help_page(title, topic="General", body=""):
    topic = HelpTopic.objects.get(title=topic)

    ContentType.objects.get_for_model(ImageAsset)
    return HelpPage.objects.create(title=title, body=body, topic=topic, published=True)


def help_build():
    call_command("sync_help_items")
    pages = [
        build_help_page(
            title="How do I know if I'm ready to do a Dioptra analysis?",
            topic="General",
            body=get_help_body(),
        )
    ]
    for title, topic in blank_pages:
        pages.append(build_help_page(title=title, topic=topic))

    return {
        "help_pages": pages,
    }
